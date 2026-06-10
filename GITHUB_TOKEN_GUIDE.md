# 如何生成 GitHub Personal Access Token

## 步骤 1: 打开 GitHub Settings

访问: https://github.com/settings/tokens

## 步骤 2: 点击 "Generate new token"

选择 "Classic" 或 "Fine-grained tokens"

## 步骤 3: 配置 Token

**名称**: `customer-service-agent-deploy`

**过期时间**: 建议选择 90 天或更长

**权限** (勾选以下选项):
- ✅ `repo` (完整仓库访问权限)
  - ✅ `repo:status`
  - ✅ `repo_deployment`
  - ✅ `public_repo`
  - ✅ `repo:invite`
- ✅ `workflow` (如果需要 GitHub Actions)

## 步骤 4: 生成并复制 Token

点击 "Generate token" 按钮

**⚠️ 重要**: Token 只会显示一次，请立即复制保存！

## 步骤 5: 使用 Token 登录

复制 Token 后，运行以下命令:

```bash
gh auth login --with-token <<< "YOUR_TOKEN_HERE"
```

或者:

```bash
echo "YOUR_TOKEN_HERE" | gh auth login --with-token
```

## 示例 Token 格式

```
ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Token 以 `ghp_` 开头，共 40 个字符。
