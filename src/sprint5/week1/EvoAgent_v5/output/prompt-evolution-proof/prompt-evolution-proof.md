# EvoAgent 提示词版本进化回放证明

## 结论

- 进化决策：`activated`
- 数值门禁：`PASS`
- 生产来源门禁：`FAIL`
- 生产激活：`BLOCKED`

> 本报告证明受控离线环境中的行为版本进化，不证明外部 LLM 权重提升，也不代表真实 GitHub PR 的生产效果。

## 数据与反馈

- 样本：130（Validation 104 / Holdout 26）
- 仓库：10
- 来源：`offline-fixture`
- Validation 漏报反馈：32
- 自动学习规则：`REL-UNBOUNDED-RETRY`, `SEC-INSECURE-COOKIE`, `SEC-PATH-TRAVERSAL`, `SEC-WEAK-HASH`

## Validation 回放

| 指标 | Prompt v1 | Prompt v2 | 变化 |
|---|---:|---:|---:|
| Precision | 100.00% | 100.00% | +0.00 pp |
| Recall | 50.00% | 100.00% | +50.00 pp |
| F1 | 66.67% | 100.00% | +33.33 pp |
| 高风险召回率 | 75.00% | 100.00% | +25.00 pp |
| 干净样本准确率 | 100.00% | 100.00% | +0.00 pp |
| 综合得分 | 78.33% | 100.00% | +21.67 pp |

## Holdout 回放

| 指标 | Prompt v1 | Prompt v2 | 变化 |
|---|---:|---:|---:|
| Precision | 100.00% | 100.00% | +0.00 pp |
| Recall | 50.00% | 100.00% | +50.00 pp |
| F1 | 66.67% | 100.00% | +33.33 pp |
| 高风险召回率 | 75.00% | 100.00% | +25.00 pp |
| 干净样本准确率 | 100.00% | 100.00% | +0.00 pp |
| 综合得分 | 78.33% | 100.00% | +21.67 pp |

## 审计证据

- Evolution run：`32d55718-c440-4e1f-87cc-5770a3781b9c`
- 原因：candidate improved on validation and passed the non-regression holdout gate
- Prompt v1：active=`false`，parent=`None`，SHA-256=`7744079c9edf276b4855958d232aff16e93c6623d8d3812a49b8ddcfb209eceb`
- Prompt v2：active=`true`，parent=`1`，SHA-256=`7196ddb52155720265071ea96f91d934cbc3a5388b52726fd368680a86c3dc66`
- 完整数据集指纹：`1da5854b5481b275a37c9d4ae1a74c79815bbd839ed3298a08f6238ce3fe811b`
- Validation 数据指纹：`bfe8b79dfb075097742301de1ef092cf2c528aed79d0212f292d8a30c2183487`
- Holdout 数据指纹：`eca12b9d10f2ed6d9fbd9e00a6f90b7a2f967c46f0312bc91ad29676f03b5374`
