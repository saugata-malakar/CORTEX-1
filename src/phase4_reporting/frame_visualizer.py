import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import Image

def generate_2d_building_frame(stories: int = 3, bays: int = 4) -> Image:
    """Generate a 2D structural frame blueprint elevation and return a ReportLab Image."""
    fig, ax = plt.subplots(figsize=(7, 4), facecolor='#0B1D3A')
    ax.set_facecolor('#0B1D3A')
    
    bay_width = 10.0
    story_height = 6.0
    
    total_width = bays * bay_width
    total_height = stories * story_height
    
    # Draw background grid
    ax.grid(True, color='#1A365D', linestyle=':', linewidth=0.8)
    
    # Draw Columns
    for b in range(bays + 1):
        x = b * bay_width
        ax.plot([x, x], [0, total_height], color='#E0EAF5', linewidth=4.0, zorder=3)
        # Foundation footing
        ax.plot([x - 1.2, x + 1.2], [-0.5, -0.5], color='#A5D8FF', linewidth=5.0, solid_capstyle='butt', zorder=2)
        ax.plot([x, x], [-0.5, 0], color='#A5D8FF', linewidth=4.0, zorder=2)
        
    # Draw Beams / Floors
    for s in range(stories + 1):
        y = s * story_height
        ax.plot([0, total_width], [y, y], color='#E0EAF5', linewidth=3.5, zorder=3)
        if s > 0:
            # Slab indicator (thinner line above beam)
            ax.plot([0, total_width], [y + 0.3, y + 0.3], color='#A5D8FF', linewidth=1.5, alpha=0.7, zorder=2)
            
    # Ground line
    ax.plot([-bay_width*0.5, total_width + bay_width*0.5], [0, 0], color='#FFFFFF', linewidth=2.0, linestyle='--', zorder=1)
    
    # Labels and Titles
    ax.text(total_width / 2, total_height + story_height * 0.3, "2D STRUCTURAL FRAME ELEVATION", 
            color='#FFFFFF', fontsize=12, fontweight='bold', ha='center')
            
    infotext = f"STORIES: {stories} (G+{stories-1})\nBAYS: {bays}\nTYPICAL BAY WIDTH: {bay_width}m\nSTORY HEIGHT: {story_height}m"
    props = dict(boxstyle='round,pad=0.4', facecolor='#0D2C54', edgecolor='#1F4E5B', alpha=0.85)
    ax.text(-bay_width*0.4, total_height, infotext, color='#5EC4E2', fontsize=7, fontfamily='monospace', 
            bbox=props, zorder=10, va='top', ha='left')
            
    # Dimension lines
    ax.annotate('', xy=(-bay_width*0.2, 0), xytext=(-bay_width*0.2, total_height),
                arrowprops=dict(arrowstyle='<->', color='#7F8C8D', shrinkA=0, shrinkB=0))
    ax.text(-bay_width*0.25, total_height/2, f"{total_height}m", color='#7F8C8D', rotation=90, va='center', ha='center', fontsize=8)
    
    ax.annotate('', xy=(0, -story_height*0.3), xytext=(total_width, -story_height*0.3),
                arrowprops=dict(arrowstyle='<->', color='#7F8C8D', shrinkA=0, shrinkB=0))
    ax.text(total_width/2, -story_height*0.4, f"{total_width}m", color='#7F8C8D', va='top', ha='center', fontsize=8)
    
    # Cleanup axes
    ax.set_xlim(-bay_width*0.5, total_width + bay_width*0.5)
    ax.set_ylim(-story_height*0.8, total_height + story_height*0.8)
    ax.set_xticks([])
    ax.set_yticks([])
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    
    return Image(buf, width=400, height=230)
