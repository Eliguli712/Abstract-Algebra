# 庞加莱圆盘与上半平面：映射及着色说明

## 1. 几何对象与反射

程序从种子多边形出发，对边所在的双曲测地线作反射，并以广度优先队列收集有限数量的多边形。非直径测地线由与单位圆正交的欧氏圆表示：

$$
|z-c|^2=R^2,\qquad |c|^2-R^2=1.
$$

在该测地线上的反射为

$$
s(z)=c+\frac{R^2}{\overline{z-c}}.
$$

方向为 $e^{i\theta}$ 的直径使用反射 $s(z)=e^{2i\theta}\overline z$。这些反射是圆盘的反全纯等距变换，复合反射提供与群作用相关的计算实验。

默认保留原有种子构造及 `p=4, q=5` 参数。严格正则铺砌所需的顶点角、顶点配价与群关系验证属于额外的几何检查。默认 `use_ideal_endpoints=True` 将选定边的端点分别沿径向投到单位圆，再绘制通过这两个理想端点的测地线；由此得到的圆弧参与最终分区。

## 2. 左右两图的精确变换

选择竖直直径作为对应轴，先旋转 $u=-iz$，再使用 Cayley 变换：

$$
A(z)=i\frac{1-iz}{1+iz},\qquad
A^{-1}(w)=i\frac{w-i}{w+i}.
$$

其中 $|z|<1$ 对应 $\operatorname{Im}w>0$，圆盘中心 $z=0$ 对应 $w=i$。竖直直径 $z=it$ 映射到虚轴：

$$
A(it)=i\frac{1+t}{1-t},\qquad -1<t<1.
$$

上半平面的每个采样位置通过 $A^{-1}$ 回查圆盘中同一份颜色光场。线条按可见测地线段单独采样，因此几何变换可精确对应，光栅填充会保留有限分辨率误差。

## 3. 分隔深度与区域颜色

程序首先在圆盘栅格上以圆弧作为墙，标记连通区域。每块区域选取内部代表点 $z_C$，相对于靠近圆心的基点 $z_0$ 定义分隔计数：

$$
d(C)=\sum_{g\in\mathcal G}
\mathbf{1}\{g\text{ 将 }z_C\text{ 与 }z_0\text{ 分隔}\}.
$$

$\mathcal G$ 是当前准备绘制的圆弧记录。程序中的 `depth` 与图注中的递归深度采用这一着色指标；反射生成队列的层数以及群中的最短字长需要单独计算。

径向坐标由双曲距离归一化得到：

$$
\rho(z_C)=2\operatorname{artanh}|z_C|,\qquad
t(C)=\frac{\min(\rho(z_C),\rho_{\max})}{\rho_{\max}}.
$$

基色还使用代表点的角位置与确定性区域相位，所以同一深度仍有颜色变化。HSV 色相在色环上混合，可平滑跨过色相端点。

## 4. 边界均色与内部柔光

当前实现按以下顺序生成颜色：

1. 从分隔深度、径向位置、角位置和区域相位计算临时基色。
2. 沿每条圆弧的两侧采样邻近区域，将圆弧半径所编码的色相与附近基色协调。
3. 对采到的边界线颜色求每块区域的均值，反馈到该区域的最终颜色。微小区域及靠外区域采用较高反馈权重。
4. 用区域内部到边界的距离形成连续光场：窄幅内缘略深，中心缓慢柔亮。
5. 根据最终区域颜色再次协调描线，加入低透明度、较宽的同色辉光。

边界均值是有限采样的颜色均值。反馈采用单次计算，再生成最终描线；它没有求解填充色与描线色相互依赖的固定点方程。缺少有效边界采样的区域沿用自身基色。

RGB 量化后，颜色查找表会以很小的确定性偏移消除重复三元组。这保证被填充区域的查找表颜色互异；邻近像素经渐变、插值及混合后的显示颜色仍可能相同。

## 5. 运行参数

先安装根目录的 `requirements.txt`，并建立输出目录。

| 参数 | 含义 | 默认值 |
| --- | --- | --- |
| `-o` / `--output` | 输出文件路径，父目录须存在 | 程序旁的 `poincare_inversion_correspondence.png` |
| `-p` / `--palette` | 命名配色 | `adaptive-rainbow` |
| `--raster` | 圆盘分区栅格边长 | `2600` |
| `--hue-mode` | HSV 色环或有界色相渐变 | 随配色预设 |
| `--hue H0 H1` | 起止色相 | 随配色预设 |
| `--hue-cycles` | 自适应色环圈数 | 随配色预设 |
| `--angular-hue-span` | 有界色相模式中的角向变化幅度 | 随配色预设 |
| `--cell-hue-jitter` | 确定性区域色相扰动 | 随配色预设 |
| `--sat S0 S1` | 饱和度起止值 | 随配色预设 |
| `--val V0 V1` | 明度起止值 | 随配色预设 |

`--hue-gamma`、`--sat-gamma`、`--val-gamma` 调整对应通道渐变曲率；相应的 `--*-depth-weight` 控制分隔深度与径向坐标的混合比例。自适应彩虹模式使用单独的环形色相公式，色相渐变曲率及深度权重供有界 `ramp` 模式使用。完整选项见 `--help`。

Python 中可直接调用：

```python
from pathlib import Path
import matplotlib.pyplot as plt
from poincare_face_shading_2 import CELL_PALETTES, render_pair

Path("outputs").mkdir(exist_ok=True)
palette = CELL_PALETTES["adaptive-rainbow"].replace(
    saturation=(0.34, 0.68),
    value=(0.98, 0.80),
)
fig, axes, stats = render_pair(
    output_path="outputs/poincare_custom.png",
    palette=palette,
    raster_n=2600,
)
print(stats)
plt.close(fig)
```

## 6. 分辨率与图例口径

默认允许面积至少为 1 个栅格像素、代表点半径不超过 `0.997` 的有效区域参与填充。进一步提高栅格分辨率可识别更多细小区域；数学上的无穷细结构由有限采样近似。

圆弧色条标出半径 $R$ 所给出的基础色相，二维 HSV 图例展示固定角度下的基色切片，角向色带展示层内色相变化。最终显示颜色还含边界反馈与内部光照，因此这些图例表示基础编码。

默认图包含大量圆弧分段与高分辨率图像，运行时会占用数 GB 内存。建议先以 `--raster 1600` 检查配色，再采用默认分辨率导出。SciPy 提供连通域标记和距离变换，已列为复现环境依赖。

## 7. 验证指标

程序运行后打印：

- `roundtrip_max_abs_error`：Cayley 正逆变换的最大往返误差。
- `mapped_vertical_diameter_max_abs_Re_w`：选定竖直直径映射后偏离虚轴的量。
- `cells_filled`、`microcells_filled_area_le_5px`：被填充区域及微小区域数。
- `same_depth_exact_color_collisions`：同深度查找表的量化 RGB 颜色碰撞；空字典表示无碰撞。

这些指标检查变换、光栅分区与颜色编码。区域数量受栅格分辨率、NumPy、Matplotlib 和 SciPy 的数值行为影响。
