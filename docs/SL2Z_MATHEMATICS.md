# 上半平面中的模群展开

上半平面为 ℍ={x+iy:y>0}，双曲度量为 ds²=(dx²+dy²)/y²。
若整数矩阵 g=[a b;c d] 满足 ad−bc=1，则

$$
g\cdot z=\frac{az+b}{cz+d},\qquad
\operatorname{Im}(g\cdot z)=\frac{\operatorname{Im}z}{|cz+d|^2}.
$$

使用生成元 S=[0 −1;1 0]、T=[1 1;0 1]，分别作用为 −1/z 与 z+1。
矩阵群中 S²=(ST)³=−I。g 与 −g 的作用相同，因此区域按 PSL₂(ℤ) 规范化去重。

闭标准基本域为

$$
\mathcal F=\{z\in\mathbb H:|\operatorname{Re}z|\leq\tfrac12,\ |z|\geq1\}.
$$

两条竖直边由 T 配对，单位圆弧的两半由 S 配对。
顶角为 ρ=−1/2+i√3/2、ρ+1，另有尖点 ∞。
每个 gℱ 的双曲面积为 π/3，内部互不相交，闭区域可在边界重合。
图中点 i 是 S 的固定点；其他标记节点来自两个顶角的轨道。
当 c≠0，gℱ 的尖点为 a/c；c=0 时为 ∞。

边界以与实轴正交的圆弧及竖直线表示。
通过 p,q 的非竖直支撑圆的圆心位于实轴，坐标为

$$
x_0=\frac{|p|^2-|q|^2}{2(\operatorname{Re}p-\operatorname{Re}q)}.
$$

## 有限深度

由 I 开始，按 S、T、T⁻¹ 右乘进行广度优先搜索。
整体符号去重后的队列深度，是这组生成元下的最短字长。
逐区滑杆遵循这一固定次序。互动生成元按钮左乘当前矩阵。

| 深度上限 | 累计区域数 |
| --- | ---: |
| 0 | 1 |
| 4 | 36 |
| 8 | 282 |
| 12 | 1,968 |
| 16 | 13,524 |
| 18 | 35,416 |

画面裁去视窗外和亚像素区域；数学铺砌向实轴方向持续细分。
边界上的点可属于多个闭基本域，点选还原算法使用固定取整及圆周容差选取一个代表。
实轴及尖点属于边界。

原有庞加莱绘图程序的深度采用有限圆弧相对于基点的分隔计数。
本互动模块的深度采用生成元的最短字长；两者各有明确的计算定义。

核对资料：

- Keith Conrad, SL₂(ℤ), §§1–2：https://kconrad.math.uconn.edu/blurbs/grouptheory/SL(2,Z).pdf
- Gabor Wiese, Vorlesung über Modulformen, §3.1：https://math.uni.lu/wiese/notes/MF.pdf
