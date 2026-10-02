# notebooks — 探索性分析

```
notebooks/
├── cmj/      # 陈明进
└── ly/       # 李云
```

## 命名

```
YYYYMMDD-作者-主题.ipynb
例：20261002-cmj-retraction-trend.ipynb
```

按日期排序即按时间线排序，方便回溯"这个图是哪天做的"。

## 提交前清空输出

notebook 的输出会进 git，而且无法增量压缩——一张嵌入的图可能占几 MB，重跑几次仓库就大了。

```bash
jupyter nbconvert --clear-output --inplace notebooks/**/*.ipynb
```

**涉及真实人名的输出必须清空。** 表格里带出被撤稿作者姓名的结果不要提交。

## notebook 还是 .py？

- 探索阶段：notebook，快速试错
- 结论稳定、要反复跑：重写成 `code/<你的人>/` 下的模块
- notebook 里不要 import 另一个人的目录，需要共用就抽到 `code/shared/`
