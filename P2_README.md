# P2 多尺度特征匹配质量评测

本页保留最初合成代理版本的说明。当前使用 12 张实拍照片、250 对助手核对点及重新运行的结果，见 [真实照片版提交与复现](P2_REAL_README.md)。请勿把下面的旧合成数值用于新照片报告。

本材料是**合成代理数据验证版**。代码、实际运行结果、曲线及报告已配套；数据由程序生成，不满足作业的“自采至少 10 张、每图手工标注至少 20 对同名点”条件。真实照片和人工标注需要实际完成后另跑实验，不能只修改来源/状态字段。

## 文件

- 单一实现：`p2_multiscale_feature_matching.py`，P2 不依赖 `scripts/` 中的 P1 实现。
- 报告：`output/pdf/p2-report.pdf`；可编辑源：`paper/p2-report.tex`、`paper/p2-results.tex`、尺度/噪声分析 `.tex` 与共享排版配置 `paper/latex-preamble.tex`。
- 数据：`data/p2/manifest.json`、20 张 PNG、10 个标注 JSON，每对图有 32 对生成控制点。
- 真实采集模板：`data/p2/real-manifest.template.json`、`data/p2/manual-annotation.template.json`；详细操作及来源边界见 `data/p2/README.md`。
- 逐图结果和环境/输入哈希：`output/p2/`；PDF/SVG 曲线及 PNG 预览：`figures/p2/`。
- 提交说明文字：`output/p2/submission-text.txt`。
- 提交压缩包：`output/p2-submission.zip`，排除 P1 实现、临时依赖和 `.git`，仅包含一个 `.py`。

## 独立复现

建议使用 Python 3.12 的虚拟环境。P2 使用 OpenCV headless，无需 GUI、浏览器或开发服务器：

```powershell
python -m venv .venv-p2
.venv-p2\Scripts\python.exe -m pip install -r requirements-p2.txt
.venv-p2\Scripts\python.exe p2_multiscale_feature_matching.py --self-test
.venv-p2\Scripts\python.exe p2_multiscale_feature_matching.py --validate-only
.venv-p2\Scripts\python.exe p2_multiscale_feature_matching.py --data-root data/p2
```

`requirements-p2.txt` 固定本次实际使用的发行包版本，`requirements.txt` 则是整个仓库的兼容依赖。默认随机种子 `20260917`，OpenCV 单线程，最终特征预算 220。逐图输出可复核，运行时间因硬件、负载而变化。重新运行会覆盖指定的结果/图表目录，但不会自动修改 PDF 报告。

完整实验包含 2,950 行评测：

| 范围 | 配置 | 行数 |
| --- | --- | ---: |
| 主矩阵 | 10 图对 × 5 方法 × 5 预处理 × 3 深度 | 750 |
| 消融 | 10 图对 × 5 方法 × 4 开关设置 | 200 |
| 噪声 | 10 图对 × 5 方法 × 5 预处理 × 4 附加噪声强度 | 1,000 |
| 图像尺度 | 10 图对 × 5 方法 × 5 预处理 × 4 场景重采样倍率 | 1,000 |

五方法为 Sobel、LoG、Harris、Shi-Tomasi、SIFT；五预处理为不滤波、理想低通、高斯低通、理想高通、高斯高通。`full` 消融基准为高斯低通、三层、NMS 开启，其余设置分别关闭一个因素。图像尺度曲线不是金字塔深度曲线，两者分别输出。

仅生成代理数据、不执行实验：

```powershell
python p2_multiscale_feature_matching.py --generate-synthetic --generate-only
```

默认不覆盖已存在清单。仅当明确需要重建代理集时追加 `--force`。合成生成器会拒绝覆盖标为真实数据的清单；不要对自己的照片目录使用生成命令。生成图受系统字体影响，严格复现优先使用已有 PNG，并核对 `output/p2/summary.json` 中的代码、输入图像及标注 SHA-256。

## 切换真实数据

建议在被 Git 忽略的 `data/private/p2/` 内准备真实 `manifest.json`、照片及每图至少 20 对人工标注，按实际拍摄条件填写模板；涉及姓名、学号时先脱敏。照片近似平面、点对分布应覆盖全图，逐点复核后才能标记 `manual_verified`。

```powershell
python p2_multiscale_feature_matching.py --data-root data/private/p2 --require-manual --validate-only
python p2_multiscale_feature_matching.py --data-root data/private/p2 --require-manual --output-root output/p2-real --figure-root figures/p2-real
```

`--require-manual` 检查字段、样本数量、点数和坐标，不鉴定真实采集来源。当前代理集应被该选项拒绝。需要上传真实标注时，确认照片授权，再单独打包照片/标注；默认代理提交包不会包含私人目录。

## 指标与解释边界

- 重复率：共同可见区域中，按距离贪心一对一配对的 5 参考像素以内重复点数 / 两图较小点数。不是最大基数匹配。
- 匹配正确率：双向 0.78 比例检验且互为最近邻的接受匹配中，4 参考像素以内正确匹配的比例；无匹配时为未定义。汇总附有效样本数，不将未定义结果当零。
- 定位误差：重复点对误差中位数，是条件统计；另输出接受匹配的误差。应结合重复点数、接受/正确匹配数量及分布解读。
- 时间：两图的预处理、检测、描述、几何评估和匹配，排除 I/O；每图对/配置单次计时，无多次重复计时或预热。
- 四种响应采样方法使用 256 维归一化补丁描述子，SIFT 使用原生 128 维描述子，因此比较完整管线，不能据此单独排名检测器。
- SIFT 的内部 DoG 极值及尺度空间保持开启；其 NMS/金字塔消融只针对共同后处理和外部层。
- 高通包括百分位对比度映射；数字尺度曲线不等价于实际拍摄距离变化。
- 曲线误差棒是十图之间的样本标准差，不是置信区间；共享程序版式的十图不能视为十个独立真实原稿。

## 图表与报告

`repeatability_scale`、`repeatability_noise`、`repeatability_pyramid` 分别呈现场景缩放、附加噪声及外部金字塔深度的敏感性；`ablation_metrics` 呈现四项指标。每种曲线有五个预处理面板，五方法以颜色、标记和线型区分。`sample_matches.png` 为第一组图上的 SIFT 示例，绿线正确、红线错误，只绘制前 40 个接受匹配。

报告使用真实 CSV 数字而非预设结论；官方 OpenCV 教程只支撑算法定义，不支撑本代理集上的排名。实验数字随新输入变化时，应同步修改 `paper/p2-results.tex` 和报告结论再编译。已有报告不自动更新。

在 `paper/` 目录编译：

```powershell
tectonic p2-report.tex --outdir ../output/pdf
```

也可使用 XeLaTeX 连续编译两次。需要 `ctex`、`amsmath`、`booktabs`、`tabularx`、`caption` 等宏包；Windows 字体来自系统，不在仓库分发。若 Windows Tectonic 找不到字体，可参考 P1 的 Fontconfig 设置。提交时必须保留“代理验证版”声明，直至真实采集、人工标注和对应实验完成。
