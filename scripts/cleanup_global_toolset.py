
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.database import SessionLocal
from api import models

def cleanup_global_toolset():
    db = SessionLocal()
    try:
        # Find the Global ToolSet
        global_toolset = db.query(models.ToolSet).filter(
            models.ToolSet.is_global == True
        ).first()
        
        if not global_toolset:
            print("Global ToolSet not found.")
            return

        print(f"Original Global ToolSet '{global_toolset.name}' had {len(global_toolset.tool_names)} tools.")

        # Define Curated Core Tools (Truly global and low-risk/high-utility)
        core_tools = [
            "search.smart",
            "searxng.search",
            "browser.browse",
            "browser.page_source",
            "internal.search_company",
            "internal.get_company_details",
            "internal.term_lookup",
            "internal.term_explain",
            "search_shared_memory",
            "financial.get_verified_price",
            "financial.technical_analysis",
            "ods.eda_describe",
            "chinatimes.stock_rt",  # Global price access is useful but prioritized
            "chinatimes.stock_news"
        ]

        # Filter existing tools to remove TEJ and redundant AlphaVantage/Yahoo tools from Global
        # We want agents to use specialized toolsets for deep analysis
        new_tool_names = []
        for full_name in global_toolset.tool_names:
            base_name = full_name.split(':')[0]
            
            # Keep if in core list
            if base_name in core_tools:
                new_tool_names.append(full_name)
                continue
            
            # Exclude TEJ and niche AlphaVantage from Global
            if base_name.startswith("tej."):
                continue
            if base_name.startswith("av.") and base_name not in core_tools:
                # We want macro tools to be in Strategic set, not for everyone blindly
                continue
            
            # Keep others that are generic enough (e.g. google, internal)
            if base_name.startswith("google.") or base_name.startswith("internal."):
                new_tool_names.append(full_name)

        global_toolset.tool_names = list(set(new_tool_names)) # Deduplicate
        global_toolset.description = "全局核心工具集：僅包含基礎搜尋、事實查核與內部報價工具。專業數據請見專用工具集。"
        
        db.commit()
        print(f"Updated Global ToolSet now has {len(global_toolset.tool_names)} tools.")
        print("Curated Tools:", global_toolset.tool_names)

    finally:
        db.close()

if __name__ == "__main__":
    cleanup_global_toolset()
