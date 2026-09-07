# Machine Vision

P1：文档图像偏色与光照不均的技术综述及视觉数据收集方案。

## 提交材料

- [综述 PDF（LaTeX排版）](output/pdf/p1-review.pdf)
- [采集方案示意图 PNG（2880×2280）](figures/collection-plan.png)
- [完整综述 Markdown](output/review.md)
## 数据状态

数据收集方案
| 项目 | 计划数量 |
| --- | ---: |
| 独立原稿 | 24份，4类各6份 |
| 场景图像 | 24稿 × 2设备 × 5光照 = 240张 |
| 同机参考图像 | 24稿 × 2设备 = 48张 |
| 图像总量 | 288张，RAW副本、预试拍与校准伴拍不重复计数 |
| 训练/验证/测试 | 16/4/4稿，对应160/40/40张场景图 |

参考、设备变体和增强样本跟随原稿分组，避免内容泄漏。所有质量阈值是待预试校准的项目约定，不是通用行业标准。固定OCR和版面模型比较校正前后效果，不预设收益。

![视觉数据收集方案](figures/collection-plan.png)

## 可编辑文件

- [正文源稿](paper/review.md)、[结构化文献](paper/references.json)、[BibTeX](paper/references.bib)
- [可直接编译的LaTeX源文件](paper/p1-review.tex)、[LaTeX样式配置](paper/latex-preamble.tex)
- [文献核验与书目差异说明](paper/source-notes.md)
- [采集操作规范](data/collection-protocol.md)、[机器可读计划](data/collection-plan.json)
- [空白标注模板](data/annotation-template.json)：`null`表示待填，默认不允许公开。
- [示意图 HTML](figures/collection-plan.html)、[矢量 SVG](figures/collection-plan.svg)

示意图以HTML为源、内联SVG为图形，按流程图区分质检分支与返工路径。当前中文渲染使用系统字体（Microsoft YaHei/SimSun后备）；SVG在其他系统可能替换字体，PNG保持一致。无需开发服务器，HTML可直接打开。

## 复现

需要Python 3.10+、XeLaTeX或Tectonic，以及可用的Chromium、Edge或Chrome。PDF使用`ctexart`和`amsmath`，由XeTeX引擎完成中文与数学排版；示意图由Playwright渲染。Windows字体取自系统，不在仓库分发字体文件。

```powershell
python -m pip install -r requirements.txt
python scripts/build_artifacts.py --browser-channel msedge
python scripts/verify_artifacts.py
```

LaTeX引擎会从PATH查找，也可通过 `--tex-engine` 或 `P1_TEX_ENGINE` 指定路径。本次采用官方Tectonic 0.17.0 Windows便携版，运行文件与下载缓存没有提交到仓库。初次运行Tectonic需要联网按需下载TeX宏包；传统XeLaTeX环境需要安装`ctex`及所用宏包。

若使用Playwright自带的浏览器，先运行 `python -m playwright install chromium`，再运行不带 `--browser-channel` 的构建命令。其他系统会优先使用Noto CJK，再后备到Fandol字体；可在样式配置中修改字体。

只编译现有LaTeX源文件，可在 `paper/` 目录运行：

```powershell
tectonic p1-review.tex --outdir ../output/pdf
```

也可使用XeLaTeX连续编译两次以解析引文和图号。`paper/p1-review.tex`是完整生成稿；再次运行构建脚本会依据Markdown和文献JSON覆盖它，长期修改应同步到这些源文件。

已生成PNG且只改正文时，可用 `python scripts/build_artifacts.py --skip-diagram`。该选项不会更新示意图，不应用于修改示意图后的完整构建。

可选视觉复核（需Poppler）：

```powershell
New-Item -ItemType Directory -Force tmp/pdfs
pdftoppm -scale-to 1400 -png output/pdf/p1-review.pdf tmp/pdfs/review
```

生成文件位于 `output/` 与 `figures/`。
