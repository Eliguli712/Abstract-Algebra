# 语言设置 / Language settings / Spracheinstellungen

首页及三个互动页面顶部按 English → Deutsch → 中文排列语言选项，首次访问默认英文，切换即时生效。绘图参数、选区、播放状态和画布保持不变。

| 语言 | 公开首页 |
| --- | --- |
| English | https://eliguli712.github.io/Abstract-Algebra/?lang=en |
| Deutsch | https://eliguli712.github.io/Abstract-Algebra/?lang=de |
| 中文 | https://eliguli712.github.io/Abstract-Algebra/?lang=zh |

语言优先级：有效的 `lang` 链接参数 → 此浏览器保存的偏好 → English。实验入口会携带当前语言，页面顶部提供返回作品首页的链接。偏好保存不可用时，仍可通过选择器与链接切换语言。下载后的独立 HTML 同样内嵌全部翻译。

翻译覆盖标题、介绍、控件、帮助、参数、动态计数、图像替代文字和无障碍标签。数学符号、数值与几何运算保持原样。仓库中的 Markdown 技术文档继续使用中文。

## 维护与构建

- `assets/locales.json`：中文、英文、德文对应词典。
- `assets/languages.js`：语言选择、偏好、链接和动态文字处理。
- `scripts/build_languages.py`：将词典与代码内嵌到四个独立页面，可重复运行。
- `scripts/build_sl2z.py`：重建 SL₂(ℤ) 时自动内嵌语言功能。

```bash
python3 scripts/build_languages.py
```

新增可见文字时更新词典。动态文字由语言层监听并处理，避免切换后新增统计文字恢复为中文。
