"""
Manual mapping logic for player ID overrides.
"""
import pandas as pd

def apply_manual_mappings(scraped_df: pd.DataFrame, manual_mappings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Overwrites automated player matching with manual database/CSV edits.
    """
    merged_df = pd.merge(
        scraped_df,
        manual_mappings_df,
        how='left',
        left_on=['source_name', 'scraped_player_name'],
        right_on=['source_name', 'scraped_player_name']
    )
    merged_df['final_player_id'] = merged_df['true_player_id'].combine_first(merged_df['automated_player_id'])
    merged_df = merged_df.drop(columns=['true_player_id', 'automated_player_id'], errors='ignore')
    return merged_df
