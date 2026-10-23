#!/usr/bin/env python
"""
Generate horizontal bar chart showing identified vs unidentified C/H/O species
for various combustion models from literature.

Usage:
    # Run standalone with sample data:
    python species_identification_plot.py
    
    # Run with Django data:
    python manage.py shell
    >>> from importer_dashboard.static.importer_dashboard.plots.species_identification_plot import generate_plot_from_database
    >>> generate_plot_from_database()
"""

import matplotlib.pyplot as plt
import numpy as np
import os
import sys


def create_species_identification_plot(data, output_path=None, figsize=(10, 8), title=None):
    """
    Create a horizontal stacked bar chart showing identified vs unidentified species.
    
    Args:
        data: List of tuples (model_name, identified_count, total_count)
        output_path: Path to save the figure (optional)
        figsize: Figure size tuple
        title: Optional title for the plot
    
    Returns:
        matplotlib figure object
    """
    if not data:
        print("No data to plot!")
        return None
    
    models = [d[0] for d in data]
    identified = [d[1] for d in data]
    total = [d[2] for d in data]
    unidentified = [t - i for i, t in zip(identified, total)]
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Colors matching the original chart
    color_identified = '#4472C4'  # Blue
    color_unidentified = '#E8B4B8'  # Light pink/salmon
    
    y_pos = np.arange(len(models))
    
    # Create horizontal bars
    bars_identified = ax.barh(y_pos, identified, color=color_identified, 
                               label='Identified', edgecolor='none')
    bars_unidentified = ax.barh(y_pos, unidentified, left=identified, 
                                 color=color_unidentified, label='Unidentified', 
                                 edgecolor='none')
    
    # Calculate max value for positioning labels
    max_total = max(total) if total else 100
    label_offset = max_total * 0.02
    
    # Add value labels on the bars
    for i, (ident, unident, tot) in enumerate(zip(identified, unidentified, total)):
        # Label for identified (inside the bar, white text)
        if ident > max_total * 0.05:  # Only show if bar is wide enough
            ax.text(ident/2, i, str(ident), ha='center', va='center', 
                   color='white', fontsize=9, fontweight='normal')
        
        # Label for total (at the end of the bar)
        ax.text(tot + label_offset, i, str(tot), ha='left', va='center', 
               color='black', fontsize=9)
    
    # Customize the plot
    ax.set_yticks(y_pos)
    ax.set_yticklabels(models)
    ax.set_xlabel('C/H/O\nSpecies', fontsize=10)
    ax.set_xlim(0, max_total * 1.15)  # Add 15% padding for labels
    
    if title:
        ax.set_title(title, fontsize=12, fontweight='bold')
    
    # Add legend
    ax.legend(loc='upper right', frameon=True)
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add gridlines for x-axis
    ax.xaxis.grid(True, linestyle='-', alpha=0.3)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f"Plot saved to {output_path}")
    
    return fig


def generate_plot_from_database(output_path=None, show_plot=True):
    """
    Generate the species identification plot using data from Django ClusterJob models.
    
    Args:
        output_path: Path to save the figure (optional, defaults to static folder)
        show_plot: Whether to display the plot
    
    Returns:
        matplotlib figure object
    """
    # Import Django models
    try:
        from importer_dashboard.models import ClusterJob
    except ImportError:
        # Try setting up Django if not already configured
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kineticmodelssite.settings')
        django.setup()
        from importer_dashboard.models import ClusterJob
    
    # Query all jobs with species data
    jobs = ClusterJob.objects.filter(
        total_species__gt=0
    ).order_by('name')
    
    if not jobs.exists():
        print("No jobs with species data found in database!")
        return None
    
    # Build data list
    data = []
    for job in jobs:
        # Use short name (last part of path or full name)
        short_name = job.name.split('/')[-1] if '/' in job.name else job.name
        # Truncate if too long
        if len(short_name) > 30:
            short_name = short_name[:27] + '...'
        
        data.append((
            short_name,
            job.identified_species,
            job.total_species
        ))
    
    print(f"Found {len(data)} jobs with species data:")
    for name, identified, total in data:
        pct = (identified / total * 100) if total > 0 else 0
        print(f"  {name}: {identified}/{total} ({pct:.1f}%)")
    
    # Set default output path
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'species_identification_chart.png'
        )
    
    # Adjust figure size based on number of jobs
    fig_height = max(6, len(data) * 0.5)
    
    # Create the plot
    fig = create_species_identification_plot(
        data, 
        output_path=output_path,
        figsize=(10, fig_height),
        title='Species Identification Progress by Model'
    )
    
    if show_plot:
        plt.show()
    
    return fig


# Sample data from the original chart (for standalone testing)
SAMPLE_DATA = [
    ("Veloo p.599", 113, 113),
    ("Sheen p.527", 113, 121),
    ("Darcy p.411", 852, 877),
    ("Liu p.401", 137, 137),
    ("Malewicki p.361", 1686, 1924),
    ("Malewicki p.353", 380, 1924),
    ("Wang p.335", 1064, 1350),
    ("Husson p.325", 202, 202),
    ("Herbinet p.297", 488, 662),
    ("Dagaut p.289", 296, 355),
    ("Matsugi p.269", 94, 277),
    ("Labbe p.259", 125, 125),
    ("Somers p.225", 335, 392),
]


if __name__ == '__main__':
    # Check if running with Django
    use_django = '--django' in sys.argv or '-d' in sys.argv
    
    if use_django:
        # Set up Django
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kineticmodelssite.settings')
        
        import django
        django.setup()
        
        generate_plot_from_database()
    else:
        # Use sample data (reversed to match image order - top to bottom)
        data = SAMPLE_DATA[::-1]
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(script_dir, 'species_identification_chart.png')
        
        fig = create_species_identification_plot(data, output_file)
        plt.show()
        
    print("Plot generated successfully!")
