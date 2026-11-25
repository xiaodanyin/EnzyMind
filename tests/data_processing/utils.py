import os
import pandas as pd

def save_sequences_as_fasta(input_file, output_dir):
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    sequence_counter = 1

    with open(input_file, 'r') as file:
        for line in file:
            parts = line.strip().split()  # 假设每部分由空格分隔
            if len(parts) != 3:
                continue  # 如果行格式不正确，则跳过这行
            # uniprot_id = parts[0]
            # label = parts[1]
            sequence = parts[2]
            
            # 创建文件名和文件路径
            filename = f"{sequence_counter}.fasta"
            filepath = os.path.join(output_dir, filename)
            
            # 将序列写入文件
            with open(filepath, 'w') as fasta_file:
                fasta_file.write(f">sequence\n")  # 写入标识行
                fasta_file.write(sequence + '\n')  # 写入序列

            sequence_counter += 1

def save_csv_sequences_as_fasta(input_file, output_dir):
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    sequence_counter = 1

    sequence_df = pd.read_csv(input_file)
    for i in range(len(sequence_df)):
            row = sequence_df.iloc[i]
            # uniprot_id = row['Uniprot ID']
            # binding = row['Binding']
            # ecnumber = row['EC']
            sequence = row['aa_sequence']
            # sequence = row['Sequences']
            
            # 创建文件名和文件路径
            filename = f"{sequence_counter}.fasta"
            filepath = os.path.join(output_dir, filename)
            
            # 将序列写入文件
            with open(filepath, 'w') as fasta_file:
                fasta_file.write(f">sequence\n")  # 写入标识行
                fasta_file.write(sequence + '\n')  # 写入序列

            sequence_counter += 1

# 使用此函数处理您的文件
input_file = '../../enzyme_agent/data/active_site_prediction_test_data/select_enzyme_active_site_prediction_test_data.csv'
# input_file = '../../enzyme_agent/data/substrate_prediction_test_data/select_enzyme_substrate_determination_test_data.csv'  # 请替换为实际的文件路径
output_dir = '../../enzyme_agent/data/active_site_prediction_test_data/fasta_file'  # 您可以定义输出目录
save_csv_sequences_as_fasta(input_file, output_dir)
# save_sequences_as_fasta(input_file, output_dir)


