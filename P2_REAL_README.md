# P2 真实照片实验与提交材料

本版使用用户提供的 12 张教材书页照片，参考图为 `IMG_0260.JPG`，其余 11 张与参考配对。助手视觉选点、局部灰度配准辅助及逐点放大图核对后，共保留 250 对同名点，每图 20–24 对。原照片未修改，工作照片统一为 960×1280，并去除 EXIF/GPS 元数据。

来源边界：这是教材页，不是题目指定的板书/试卷；标注执行者和复核者为助手，状态为 `assistant_visual_verified`、`human_verified=false`，不冒充学生亲手标注。程序的 `--require-manual` 会拒绝这些标注。数量与实验材料已完成，不意味着这两项字面要求已完全满足。

## 提交文件

- 真实照片版报告：`output/pdf/p2-report-real.pdf`。
- 完整提交包：`output/p2-real-submission.zip`，仅含一个 `.py`，包含工作照片、最终标注、曲线、结果、报告及复现说明。
- 唯一 P2 实现：`p2_multiscale_feature_matching.py`。
- 照片与标注：`data/private/p2/`，受 Git 忽略，但显式收入本版提交包。
- 初选点及排除记录：`data/p2-real-landmarks.json`；助手复核记录：`data/p2-annotation-review.json`。
- 结果与输入哈希：`output/p2-real/`；图表、逐点放大核对图、几何质量记录：`figures/p2-real/`。
- 成果说明文字：`output/p2-real/submission-text.txt`。
- 报告可编辑源：`paper/p2-report-real.tex`、`paper/p2-real-results.tex` 和共享排版配置。

此前 `data/p2/`、`output/p2/`、`figures/p2/` 与 `p2-report.pdf` 是保留的合成代理验证材料，不是本版真实照片结果。本版提交包不混入代理图片或 P1 实现。

## 独立复现

建议 Python 3.12，依赖版本固定在 `requirements-p2.txt`。照片与最终标注通过 ZIP 分发，不单独跟踪 `data/private/p2/`。从 GitHub 克隆仓库后，先把 `output/p2-real-submission.zip` 解压到独立目录，再在解压后的根目录运行以下命令；本地已有工作数据的仓库根目录也可直接运行：

```powershell
python -m pip install -r requirements-p2.txt
python p2_multiscale_feature_matching.py --self-test
python p2_multiscale_feature_matching.py --data-root data/private/p2 --validate-only
python p2_multiscale_feature_matching.py --data-root data/private/p2 --figure-root figures/p2-real --render-annotations
python p2_multiscale_feature_matching.py --data-root data/private/p2 --output-root output/p2-real --figure-root figures/p2-real
```

照片和标注均已在提交包内，不需要原始 D 盘路径。最终 JSON 是复现优先输入。随机种子 `20260917`，OpenCV 单线程，最终特征预算 220。再次运行会覆盖指定结果/图表目录，不会自动更新 PDF 报告中的数字；运行时间随硬件负载变化。

完整实验共 3,245 行：

| 范围 | 配置 | 行数 |
| --- | --- | ---: |
| 主矩阵 | 11 图对 × 5 方法 × 5 预处理 × 3 深度 | 825 |
| 消融 | 11 图对 × 5 方法 × 4 设置 | 220 |
| 噪声曲线 | 11 图对 × 5 方法 × 5 预处理 × 4 噪声强度 | 1,100 |
| 数字尺度曲线 | 11 图对 × 5 方法 × 5 预处理 × 4 缩放倍率 | 1,100 |

方法为 Sobel、LoG、Harris、Shi-Tomasi、SIFT。频域设置为不滤波、理想低通、高斯低通、理想高通、高斯高通。完整消融设置为高斯低通、三层、NMS 开启，其他设置分别关闭一项。

## 数据与标注说明

所有图对统一评测左页的标注点凸包，避免背景主导检测。在预算分配前限制 ROI 候选点，不将图像背景清零，FFT 仍作用于完整图像。不同图对凸包可能略有差异，各图对内的配置保持同一范围。

坐标是工作照片左上角为原点的 `[x,y]`；JSON 同时提供原图等效坐标、初选坐标和局部配准分数。点号可以不连续，删除的点不以生成点补齐。`IMG_0265` 使用 20 对，`IMG_0268` 使用 20 对，其余为 22–24 对。助手辅助标注不经过被测五类检测器生成。

单应矩阵由保留点对最小二乘拟合。`figures/p2-real/annotation-quality.json` 给出拟合 RMSE、最大残差和留一误差；这些不等于独立人工真值精度。书页弯曲使平面模型近似，部分残差接近或超过指标阈值。局部灰度匹配分数也不是概率。报告已讨论这些误差对匹配可信度的影响。

重新导入原图属于数据重建，会重写工作照片和标注，并使原有助手复核状态失效。仅在确有需要时运行：

```powershell
python p2_multiscale_feature_matching.py --prepare-photos "D:\计算机视觉\图片收集" --data-root data/private/p2 --generate-only
python p2_multiscale_feature_matching.py --data-root data/private/p2 --figure-root figures/p2-real --refine-annotations
```

重新检查全部放大图后才能应用实际完成的助手复核记录；该操作仍不产生人类手工标注认证。工作照片目录保持 Git 忽略；按用户授权发布的提交包、报告及标注预览包含工作照片内容，但不包含原始分辨率照片和 EXIF/GPS 元数据。Git 忽略不等于提交包内照片不公开。

## 指标与解释

- 重复率：共同图像/ROI 可见区域中，5 参考工作像素以内的距离升序贪心一对一配对数，除以两图较小点数。
- 匹配正确率：双向 0.78 比例检验且互为最近邻的接受匹配中，4 参考工作像素以内的比例。无接受匹配时未定义，汇总只平均有限值并列有效图数。
- 定位误差：重复点对的误差中位数，是阈值内条件统计，必须结合重复数量解读。
- 时间：两图预处理、检测、描述、几何评估和匹配的单次计时，排除 I/O。
- 四种响应方法使用归一化补丁描述子；SIFT 使用原生描述子。比较完整管线，不是检测器的纯粹排名。
- SIFT 内部尺度空间及极值保留，关闭的仅是外部金字塔/共同 NMS。高通含对比度映射。
- 曲线误差棒为 11 图对之间的样本标准差，不是独立原稿的置信区间；数字缩放/噪声是受控后处理，不是新的实拍。

## 报告编译

在 `paper/` 目录用 Tectonic 或 XeLaTeX 编译 `p2-report-real.tex`。需中文字体和 `ctex`、`amsmath`、`booktabs` 等宏包；字体不随包分发。PDF 已编译，正常提交不需要再安装 LaTeX。
