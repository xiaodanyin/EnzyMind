import pandas as pd 
import random
import numpy as np

test_df = pd.read_csv('../../enzyme_agent/data/active_site_prediction_test_data/uniprot_ecreact_merge.csv')
print(test_df.head())

# Create a sequence length column
test_df['Seq_Length'] = test_df['aa_sequence'].apply(len)

# Define the bins for the sequence length
bins = np.linspace(20, 600, 34)  # Creating 30 bins for the range 0-600

# Use pd.cut to bin sequence length
test_df['length_bin'] = pd.cut(test_df['Seq_Length'], bins, labels=False, include_lowest=True)

# Fix the random seed for reproducibility
np.random.seed(42)

# Now sampling evenly across these bins
selected_entries = []
for b in range(len(bins)-1):
    bin_entries = test_df[test_df['length_bin'] == b]
    if not bin_entries.empty:
        # Set random_state to a fixed number to reproduce the same sample each run
        sample = bin_entries.sample(min(len(bin_entries), 1), random_state=42)  
        selected_entries.append(sample)

# Concatenate all sampled entries into a single DataFrame
result_df = pd.concat(selected_entries) if selected_entries else pd.DataFrame()
print(result_df.head())

result_df.to_csv('../../enzyme_agent/data/active_site_prediction_test_data/select_enzyme_active_site_prediction_test_data.csv', index=False, encoding='utf-8')