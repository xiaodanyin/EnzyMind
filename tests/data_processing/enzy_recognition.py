import random

def select_uniformly_distributed_sequences(file_path, output_file, max_length=600, num_sequences=30, num_bins=10, seed=42):
    # 设置随机数种子以保持随机选择的一致性
    random.seed(seed)
    
    # 计算每个区间的长度
    bin_size = max_length // num_bins
    bins = [[] for _ in range(num_bins)]

    # 读取文件并根据序列长度将序列分配到不同的区间
    with open(file_path, 'r') as file:
        for line in file:
            parts = line.strip().split('\t')
            sequence = parts[2]
            length = len(sequence)
            if length < max_length:
                bin_index = length // bin_size
                if bin_index == num_bins:
                    bin_index -= 1  # 处理边界情况
                bins[bin_index].append(line.strip())

    # 尽可能均匀地从每个区间选择序列
    selected_sequences = []
    sequences_per_bin = max(1, num_sequences // num_bins)

    for bin in bins:
        if len(bin) > sequences_per_bin:
            selected_sequences.extend(random.sample(bin, sequences_per_bin))
        else:
            selected_sequences.extend(bin)

    # 如果选取的序列不足，尝试从其他区间补足
    if len(selected_sequences) < num_sequences:
        remaining_sequences = [seq for bin in bins for seq in bin if seq not in selected_sequences]
        selected_sequences.extend(random.sample(remaining_sequences, min(len(remaining_sequences), num_sequences - len(selected_sequences))))

    # 保存选中的序列到新文件
    with open(output_file, 'w') as outfile:
        for seq in selected_sequences[:num_sequences]:  # 确保不超出所需数量
            outfile.write(seq + '\n')

    return output_file

# 使用此函数处理您的文件并保存结果
output_file = select_uniformly_distributed_sequences('../../chemcrow/data/enzyme_recognition_test_data/ur100_test_swiss_filtered_22846_add_label_add_seq.txt', '../../chemcrow/data/enzyme_recognition_test_data/selected_enzyme_recognition_test_sequences.txt')
print(f"Selected sequences saved to {output_file}")
