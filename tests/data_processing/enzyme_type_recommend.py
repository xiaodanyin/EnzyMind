import pandas as pd
import os

# Read the original test data
input_file = '/raid/home/yaoxj/xdyin/work/enzyme_agent/enzyme_agent/data/enzyme_type_recommend_test_data/test.csv'
output_dir = '/raid/home/yaoxj/xdyin/work/enzyme_agent/enzyme_agent/data/enzyme_type_recommend_test_data/test_30'
output_file = os.path.join(output_dir, 'test.csv')

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Read the CSV file
df = pd.read_csv(input_file)

# Randomly sample 30 records
# sampled_df = df.sample(n=30, random_state=42)
sampled_df = df.sample(n=30, random_state=1029)

# Save the sampled data
sampled_df.to_csv(output_file, index=False)

print(f"Successfully sampled 30 records and saved to {output_file}")
