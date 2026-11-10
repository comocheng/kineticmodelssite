"""
Contribution API views for ChemKED and Chemkin file submissions.

Provides REST endpoints for uploading files that:
1. Validate against PyKED schema locally
2. Create a GitHub PR with ORCID metadata

Nothing is written to the database here. As for every route that enters
experimental data, a dataset is loaded after its pull request is merged
(chemked-ingest workflow, sync_chemked).
"""

import logging
import re
import os

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiResponse, extend_schema

logger = logging.getLogger(__name__)

ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


class ContributionSerializer(serializers.Serializer):
    """Serializer for contribution payload."""

    contributor_name = serializers.CharField(max_length=200)
    contributor_orcid = serializers.RegexField(
        regex=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$",
        help_text="ORCID in 0000-0000-0000-000X format",
    )
    file_type = serializers.ChoiceField(
        choices=["chemked", "chemkin"],
        default="chemked",
    )
    description = serializers.CharField(required=False, default="", allow_blank=True)
    run_pyteck = serializers.BooleanField(required=False, default=False)


class ContributeFilesView(APIView):
    """
    POST /api/contribute/

    Upload ChemKED YAML or Chemkin files to create a contribution PR.

    Multipart form data with fields:
      - contributor_name (str): Display name
      - contributor_orcid (str): ORCID identifier
      - file_type (str): 'chemked' or 'chemkin'
      - description (str, optional): PR description
      - run_pyteck (bool, optional): Trigger PyTeCK CI
      - files (file[]): One or more files to contribute

    The files are added to the database when the pull request is merged.
    """

    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["contribute"],
        summary="Upload ChemKED/Chemkin files and open a contribution PR",
        request=ContributionSerializer,
        responses={201: OpenApiResponse(description="Contribution PR created")},
    )
    def post(self, request):
        ser = ContributionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        uploaded_files = request.FILES.getlist("files")
        if not uploaded_files:
            return Response(
                {"error": "No files uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---- Step 1: Local PyKED validation (for chemked files) ----
        validation_results = []
        files_for_pr = []

        for uf in uploaded_files:
            content = uf.read()

            if data["file_type"] == "chemked":
                ok, msg = self._validate_chemked(content, uf.name)
                validation_results.append({
                    "file": uf.name,
                    "valid": ok,
                    "message": msg,
                })
                if not ok:
                    continue

            files_for_pr.append({"name": uf.name, "content": content})

        if not files_for_pr:
            return Response({
                "error": "All files failed validation.",
                "validation": validation_results,
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # ---- Step 2: Create GitHub PR ----
        try:
            from chemked_database.github_pr_service import GitHubPRService

            gh = GitHubPRService(
                token=getattr(settings, "GITHUB_TOKEN", None),
                owner=getattr(settings, "GITHUB_REPO_OWNER", None),
                repo=getattr(settings, "GITHUB_REPO_NAME", "ChemKED-database"),
            )
            for f in files_for_pr:
                f["path"] = self._determine_repo_path(
                    gh, f.pop("name"), f["content"], data["file_type"]
                )
            pr_result = gh.contribute_files(
                files=files_for_pr,
                contributor_name=data["contributor_name"],
                contributor_orcid=data["contributor_orcid"],
                file_type=data["file_type"],
                description=data["description"],
                run_pyteck=data["run_pyteck"],
            )
        except Exception as e:
            logger.exception("Failed to create GitHub PR")
            return Response({
                "error": f"Failed to create PR: {e}",
                "validation": validation_results,
            }, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "status": "in review",
            "detail": "The files are added to the database when the pull request is merged.",
            "pr_url": pr_result["pr_url"],
            "pr_number": pr_result["pr_number"],
            "branch": pr_result["branch"],
            "validation": validation_results,
            "files_contributed": len(files_for_pr),
            "paths": [f["path"] for f in files_for_pr],
        }, status=status.HTTP_201_CREATED)

    def _determine_repo_path(self, gh, filename, content, file_type):
        """Repository path for a contributed file.

        ChemKED files go where the web upload puts them: the path of the
        committed file with the same data, else the folder that matches the
        existing layout (GitHubPRService.determine_repo_path).
        """
        if file_type == "chemkin":
            return f"contributions/chemkin/{filename}"
        return gh.determine_repo_path(filename, content)

    def _validate_chemked(self, content_bytes, filename):
        """Validate ChemKED YAML content using PyKED.

        Returns (success, message).
        """
        import tempfile
        try:
            from pyked.chemked import ChemKED

            with tempfile.NamedTemporaryFile(
                suffix=".yaml", delete=False, mode="wb"
            ) as tmp:
                tmp.write(content_bytes)
                tmp.flush()
                tmp_path = tmp.name

            try:
                ck = ChemKED(tmp_path)
                return (True, f"Valid – {len(ck.datapoints)} datapoint(s)")
            finally:
                os.unlink(tmp_path)

        except ImportError:
            logger.warning("PyKED not installed – skipping local validation")
            return (True, "Skipped – PyKED not available (will be validated in CI)")
        except Exception as e:
            return (False, f"Validation failed: {e}")


class ContributionStatusView(APIView):
    """
    GET /api/contribute/status/<pr_number>/

    Check the CI validation status of a contribution PR.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["contribute"],
        summary="Check the CI validation status of a contribution PR",
        responses={200: OpenApiResponse(description="PR check-run statuses")},
    )
    def get(self, request, pr_number):
        try:
            from chemked_database.github_pr_service import GitHubPRService

            gh = GitHubPRService(
                token=getattr(settings, "GITHUB_TOKEN", None),
                owner=getattr(settings, "GITHUB_REPO_OWNER", None),
                repo=getattr(settings, "GITHUB_REPO_NAME", "ChemKED-database"),
            )
            # Fetch PR check runs
            checks = gh._api("get", f"/commits/{self._get_pr_head(gh, pr_number)}/check-runs")
            check_runs = checks.get("check_runs", [])

            results = []
            for cr in check_runs:
                results.append({
                    "name": cr["name"],
                    "status": cr["status"],
                    "conclusion": cr.get("conclusion"),
                })

            return Response({
                "pr_number": pr_number,
                "checks": results,
            })
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    def _get_pr_head(self, gh, pr_number):
        pr = gh._api("get", f"/pulls/{pr_number}")
        return pr["head"]["sha"]
