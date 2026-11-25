import pandas as pd 
import random
import numpy as np
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import requests


# test_df = pd.read_pickle('../../enzyme_agent/data/substrate_prediction_test_data/df_test_all_positive.pkl')
# print(test_df.head())

# test_df = test_df[['Uniprot ID','molecule ID', 'Binding', 'Sequence']]

# # test_df = test_df[test_df['Binding'] == 1]

# # Create a sequence length column
# test_df['Seq_Length'] = test_df['Sequence'].apply(len)

# # Define the bins for the sequence length
# bins = np.linspace(20, 600, 32)  # Creating 30 bins for the range 0-600

# # Use pd.cut to bin sequence length
# test_df['length_bin'] = pd.cut(test_df['Seq_Length'], bins, labels=False, include_lowest=True)

# # Fix the random seed for reproducibility
# np.random.seed(42)

# # Now sampling evenly across these bins
# selected_entries = []
# for b in range(len(bins)-1):
#     bin_entries = test_df[test_df['length_bin'] == b]
#     if not bin_entries.empty:
#         # Set random_state to a fixed number to reproduce the same sample each run
#         sample = bin_entries.sample(min(len(bin_entries), 1), random_state=42)  
#         selected_entries.append(sample)

# # Concatenate all sampled entries into a single DataFrame
# result_df = pd.concat(selected_entries) if selected_entries else pd.DataFrame()
# print(result_df.head())

# InChI_df = pd.read_excel('../../enzyme_agent/data/substrate_prediction_test_data/all_training_metabolites.xlsx', engine='openpyxl')

# result_df = pd.merge(result_df, InChI_df[['ID', 'InChI string']], left_on='molecule ID', right_on='ID', how='left')
# result_df.drop('ID', axis=1, inplace=True)
# print(result_df.head())

# result_df.to_csv('../../enzyme_agent/data/substrate_prediction_test_data/select_enzyme_substrate_determination_test_data.csv', index=False, encoding='utf-8')



# df = pd.read_csv("/raid/home/yaoxj/xdyin/work/enzyme_agent/enzyme_agent/data/substrate_prediction_test_data/mei_test_data/test_set_predictions.csv")
# sample_df = df.sample(n=40, random_state=42).reset_index(drop=True)

# sample_df.to_csv("/raid/home/yaoxj/xdyin/work/enzyme_agent/enzyme_agent/data/substrate_prediction_test_data/mei_test_data/sampled_test_data.csv", index=False)

# print(sample_df)

def fetch_fasta(uniprot_id, save_dir):
    fasta_path = os.path.join(save_dir, f"{uniprot_id}.fasta")
    if os.path.exists(fasta_path):
        return f"{uniprot_id} 已存在，跳过"

    url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(fasta_path, 'w') as f:
                f.write(response.text)
            return f"{uniprot_id} 下载成功"
        else:
            return f"{uniprot_id} 下载失败 (状态码: {response.status_code})"
    except Exception as e:
        return f"{uniprot_id} 下载异常: {e}"

def download_fasta_multithread(uniprot_ids, save_dir, max_workers=10):
    os.makedirs(save_dir, exist_ok=True)
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_id = {executor.submit(fetch_fasta, uid, save_dir): uid for uid in uniprot_ids}

        for future in tqdm(as_completed(future_to_id), total=len(future_to_id), desc="Downloading FASTA"):
            result = future.result()
            results.append(result)

    return results

df = pd.read_csv('/raid/home/yaoxj/xdyin/work/enzyme_agent/enzyme_agent/data/substrate_prediction_test_data/mei_test_data/sampled_test_data.csv')
# 假设 df 已经存在
uniprot_ids = df['UniProt_ID'].unique()  # 去重

save_dir = "/raid/home/yaoxj/xdyin/work/enzyme_agent/enzyme_agent/data/substrate_prediction_test_data/mei_test_data/test_fasta"
results = download_fasta_multithread(uniprot_ids, save_dir, max_workers=20)

print("下载完成，简要日志：")
for res in results:
    print(res)