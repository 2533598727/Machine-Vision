# 文献核验记录

核验日期：2026-09-07。本文是聚焦机制和方案的叙述性技术综述，不宣称覆盖全部研究，也没有执行性能实验。

10条文献的标题、作者、年份、出版物和DOI已通过Crossref元数据交叉检查；方法与数据集的关键边界另参照下列原始来源。没有复制或发布第三方论文全文。

| 条目 | 原始来源及核验重点 |
| --- | --- |
| [1] | [Buchsbaum DOI](https://doi.org/10.1016/0016-0032(80)90058-7)：1980，310(1)，1-26。 |
| [2] | [Land与McCann DOI](https://doi.org/10.1364/JOSA.61.000001)：1971，61(1)，起页1。Crossref只列起页；终页1-11为通行书目记录，未将其描述为Crossref提供的完整页码。 |
| [3] | [Jobson等 DOI](https://doi.org/10.1109/83.597272)：1997，6(7)，965-976；多尺度Retinex。 |
| [4] | [Reinhard等 DOI](https://doi.org/10.1109/38.946629)：2001，21(4)，34-41；统计色彩迁移不是深度方法。Crossref将Ashikhmin误拼为Adhikhmin，采用作者正确拼写。 |
| [5] | [FC4，CVF原始页面](https://openaccess.thecvf.com/content_cvpr_2017/html/Hu_FC4_Fully_Convolutional_CVPR_2017_paper.html)：局部估计置信度加权后得到全局照明；采用CVF页码4085-4094，Crossref/IEEE页码为330-339。 |
| [6] | [Deep White-Balance Editing，CVF原始页面](https://openaccess.thecvf.com/content_CVPR_2020/html/Afifi_Deep_White-Balance_Editing_CVPR_2020_paper.html)：处理ISP渲染后的sRGB白平衡；采用CVF页码1397-1406，Crossref/IEEE页码为1394-1403。 |
| [7] | [DocTr作者仓库](https://github.com/fh2019ustc/DocTr)：GeoTr几何模块与IllTr光照模块，后者使用DocProj训练；不将几何模块成绩移用为本方案色彩校正收益。ACM DOI对应2021年273-281页。 |
| [8] | [SSIM DOI](https://doi.org/10.1109/TIP.2003.819861)：正式刊期为2004，13(4)，600-612；DOI中的2003不是本文引用年份。 |
| [9] | [Sharma作者资料页](https://www.ece.rochester.edu/~gsharma/ciede2000/)：作者明确给出2005年2月、30(1)、21-30，另提供标准测试对。Crossref的最早在线年份2004不替代正式刊期。 |
| [10] | [MIT-Adobe FiveK官网](https://data.csail.mit.edu/graphics/fivek/)：5000张RAW自然照片，每图五位修图者以悦目为目标调整；不是文档照明的物理真值。 |

FiveK许可原文：[Adobe研究许可](https://data.csail.mit.edu/graphics/fivek/legal/LicenseAdobe.txt)、[Adobe与MIT研究许可](https://data.csail.mit.edu/graphics/fivek/legal/LicenseAdobeMIT.txt)。两者限定研究目的，要求保留版权和许可；“公开可下载”不等于无条件商用。本文未引入FiveK图像。

LoDoPaB-CT仅用于说明任务适配边界，并非本综述的校色实验数据来源。所有计划规模、时间与阈值均为本项目设计，不是引用论文报告的实验结果。
