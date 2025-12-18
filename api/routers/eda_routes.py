"""
EDA API Routes - FastAPI endpoints for exploratory data analysis.
"""
from fastapi import APIRouter, HTTPException, status
from api.eda_schemas import (
    EDADescribeRequest,
    EDADescribeResponse,
    EDAQuickPlotsRequest,
    EDAQuickPlotsResponse
)
from api.eda_service import EDAService
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eda", tags=["EDA"])

# Initialize EDA service
eda_service = EDAService()


@router.post("/describe", response_model=EDADescribeResponse)
async def describe_dataset(request: EDADescribeRequest):
    """
    Generate comprehensive EDA report for a CSV dataset.
    
    This endpoint:
    1. Loads the CSV file (with optional column filtering and sampling)
    2. Generates a ydata-profiling HTML report
    3. Creates basic visualizations (histograms, correlation matrix, boxplots)
    4. Extracts summary statistics to CSV
    
    Returns paths to all generated artifacts and metadata.
    """
    try:
        # Validate CSV path exists
        if not os.path.exists(request.csv_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CSV file not found: {request.csv_path}"
            )
        
        # Extract debate_id from csv_path (assuming format: /data/staging/{debate_id}/...)
        # If not in expected format, use a default
        path_parts = request.csv_path.split('/')
        if 'staging' in path_parts:
            staging_idx = path_parts.index('staging')
            debate_id = path_parts[staging_idx + 1] if len(path_parts) > staging_idx + 1 else "default"
        else:
            debate_id = "default"
        
        logger.info(f"Starting EDA analysis for debate_id={debate_id}, csv_path={request.csv_path}")
        
        # Run analysis
        result = eda_service.analyze(
            csv_path=request.csv_path,
            debate_id=debate_id,
            include_cols=request.include_cols,
            sample=request.sample,
            lang=request.lang
        )
        
        logger.info(f"EDA analysis completed. Generated {len(result['plot_paths'])} plots.")
        
        return EDADescribeResponse(**result)
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"EDA analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"EDA analysis failed: {str(e)}"
        )


@router.post("/quickplots", response_model=EDAQuickPlotsResponse)
async def generate_quick_plots(request: EDAQuickPlotsRequest):
    """
    Generate specific plots quickly without full profiling report.
    
    This is a lighter-weight alternative to /describe for cases where
    you only need specific visualizations.
    
    Note: This endpoint is currently a placeholder for future implementation.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Quick plots endpoint not yet implemented. Use /describe for now."
    )


@router.get("/health")
async def health_check():
    """Health check endpoint for EDA service."""
    return {
        "status": "healthy",
        "service": "EDA",
        "base_data_dir": str(eda_service.base_data_dir)
    }
