
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from api.database import SessionLocal
from api import models
import json

def assign_fred_tools():
    print("--- Assigning FRED tools to Macro Roles ---")
    db = SessionLocal()
    try:
        # 1. Find Macro Strategist & Chief Analyst ToolSets
        # We search for toolsets often assigned to these roles or just update the global/strategic ones
        
        target_roles = ["macro_strategist", "chief_analyst"]
        fred_tools = [
            "fred.search_series",
            "fred.get_series_observations",
            "fred.get_latest_release",
            "worldbank.global_inflation",
            "oecd.get_data",
            "oecd.search_datasets",
            "stockq.market_summary",
            "stockq.index_details"
        ]
        
        # 1. Update Global ToolSet
        global_toolsets = db.query(models.ToolSet).filter(models.ToolSet.is_global == True).all()
        for global_ts in global_toolsets:
            current = list(global_ts.tool_names)
            added = False
            for ft in fred_tools:
                if ft not in current:
                    current.append(ft)
                    added = True
            if added:
                global_ts.tool_names = current
                print(f"Updated Global ToolSet '{global_ts.name}' with Macro tools.")

        # 2. Update/Create Macro/Strategic toolsets
        toolsets = db.query(models.ToolSet).filter(models.ToolSet.name.ilike("%strategic%") | models.ToolSet.name.ilike("%macro%")).all()
        
        if not toolsets:
            print("No specific Macro/Strategic toolset found. Creating 'Macro Economics' toolset.")
            new_ts = models.ToolSet(
                name="Macro Economics",
                description="Authority tools for Global & US Macro data (FRED, World Bank, OECD).",
                tool_names=fred_tools,
                is_global=True
            )
            db.add(new_ts)
        else:
            for ts in toolsets:
                current = list(ts.tool_names)
                added = False
                for ft in fred_tools:
                    if ft not in current:
                        current.append(ft)
                        added = True
                if added:
                    ts.tool_names = current
                    print(f"Updated ToolSet '{ts.name}' with FRED tools.")
        
        db.commit()
        print("✅ DB Update Complete.")
    except Exception as e:
        db.rollback()
        print(f"❌ DB Update Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    assign_fred_tools()
