#!/bin/bash
# 安装 PyTorch Geometric 及其依赖
pip install torch_geometric

# 安装可选依赖
pip install pyg_lib torch_scatter torch_sparse torch_cluster torch_spline_conv -f https://data.pyg.org/whl/torch-2.4.0+cpu.html
