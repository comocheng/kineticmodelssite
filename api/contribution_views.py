"""
Contribution API views for ChemKED and Chemkin file submissions.

Provides REST endpoints for uploading files that:
1. Validate against PyKED schema locally
2. Create a GitHub PR with ORCID metadata
3. Optionally import into the local database
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
    import_to_db = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Also import into the local database after PR creation",
    )


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
      - import_to_db (bool, optional): Also import to local DB
      - files (file[]): One or more files to contribute
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
            repo_path = self._determine_repo_path(uf.name, data["file_type"])

            if data["file_type"] == "chemked":
                ok, msg = self._validate_chemked(content, uf.name)
                validation_results.append({
                    "file": uf.name,
                    "valid": ok,
                    "message": msg,
                })
                if not ok:
                    continue

            files_for_pr.append({"path": repo_path, "content": content})

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

        # ---- Step 3: Optionally import to local database ----
        import_results = []
        if data["import_to_db"] and data["file_type"] == "chemked":
            for f in files_for_pr:
                ok, msg = self._import_to_database(
                    f["content"], f["path"], data["contributor_name"]
                )
                import_results.append({"file": f["path"], "imported": ok, "message": msg})

        return Response({
            "pr_url": pr_result["pr_url"],
            "pr_number": pr_result["pr_number"],
            "branch": pr_result["branch"],
            "validation": validation_results,
            "import_results": import_results,
            "files_contributed": len(files_for_pr),
        }, status=status.HTTP_201_CREATED)

    def _determine_repo_path(self, filename, file_type):
        """Determine the repository-relative path for a contributed file."""
        # For ChemKED files, try to parse the YAML to determine fuel category
        # Fall back to a contributions/ directory
        name = os.path.splitext(filename)[0]
        if file_type == "chemkin":
            return f"contributions/chemkin/{filename}"
        return f"contributions/chemked/{filename}"

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

    def _import_to_database(self, content_bytes, filepath, contributor_name=""):
        """Import a validated ChemKED file into the local database.

        Uses the same importer as the web upload form.
        """
        try:
            from chemked_database.import_dispatcher import import_chemked_to_db

            dataset = import_chemked_to_db(
                content_bytes,
                os.path.basename(filepath),
                file_author=contributor_name,
            )
            return (True, f"Imported as dataset #{dataset.pk}")

        except Exception as e:
            logger.exception("Database import failed for %s", filepath)
            return (False, f"Import failed: {e}")


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
