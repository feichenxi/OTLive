<?php
/**
 * EXHome 提现管理 - 提现列表
 */
$login = "yes";
require("../data/class.php");
require("../data/config.php");

if (!checkAdminLogin()) {
    header("Location: ../login.php");
    exit;
}

$db = getDbConnection();

// 处理AJAX请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];
    
    switch ($action) {
        case 'approve':
            $id = intval($_POST['id'] ?? 0);
            if ($id <= 0) jsonResponse(1, '参数错误');
            
            $sql = "UPDATE withdrawals SET status = 1, handle_time = NOW() WHERE id = {$id} AND status = 0";
            if (mysqli_query($db, $sql)) {
                jsonResponse(0, '已通过');
            } else {
                jsonResponse(1, '操作失败: ' . mysqli_error($db));
            }
            break;
            
        case 'reject':
            $id = intval($_POST['id'] ?? 0);
            $reason = trim($_POST['reason'] ?? '');
            
            if ($id <= 0) jsonResponse(1, '参数错误');
            
            mysqli_begin_transaction($db);
            try {
                $sql = "UPDATE withdrawals SET status = 2, reject_reason = '{$reason}', handle_time = NOW() WHERE id = {$id} AND status = 0";
                mysqli_query($db, $sql);
                
                // 返还余额
                $sql = "SELECT user_id, amount FROM withdrawals WHERE id = {$id}";
                $result = mysqli_query($db, $sql);
                $withdraw = mysqli_fetch_assoc($result);
                
                if ($withdraw) {
                    $sql = "UPDATE users SET balance = balance + {$withdraw['amount']} WHERE id = {$withdraw['user_id']}";
                    mysqli_query($db, $sql);
                }
                
                mysqli_commit($db);
                jsonResponse(0, '已拒绝');
            } catch (Exception $e) {
                mysqli_rollback($db);
                jsonResponse(1, '操作失败');
            }
            break;
    }
}

// 获取分页参数
$pageParams = getPageParams();
$page = $pageParams['page'];
$limit = $pageParams['limit'];
$offset = $pageParams['offset'];

// 搜索条件
$where = "WHERE 1=1";
$keyword = isset($_GET['keyword']) ? trim($_GET['keyword']) : '';
$status = isset($_GET['status']) ? intval($_GET['status']) : -1;

if ($keyword) {
    $keyword_escaped = mysqli_real_escape_string($db, $keyword);
    $where .= " AND (u.nickname LIKE '%{$keyword_escaped}%' OR u.phone LIKE '%{$keyword_escaped}%')";
}

if ($status >= 0) {
    $where .= " AND w.status = {$status}";
}

// 获取总记录数
$sql = "SELECT COUNT(*) as count FROM withdrawals w LEFT JOIN users u ON w.user_id = u.id {$where}";
$result = mysqli_query($db, $sql);
$total = mysqli_fetch_assoc($result)['count'];

// 获取提现列表
$sql = "SELECT w.*, u.nickname, u.phone, u.avatar 
        FROM withdrawals w 
        LEFT JOIN users u ON w.user_id = u.id 
        {$where} ORDER BY w.create_time DESC LIMIT {$offset}, {$limit}";
$result = mysqli_query($db, $sql);
$withdrawals = array();
while ($row = mysqli_fetch_assoc($result)) {
    $withdrawals[] = $row;
}

$withdraw_status = array(
    0 => array('text' => '待审核', 'class' => 'layui-bg-orange'),
    1 => array('text' => '已通过', 'class' => 'layui-bg-green'),
    2 => array('text' => '已拒绝', 'class' => 'layui-bg-red'),
);

$setting = getSetting();
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>提现管理 - <?php print $setting['app_name']; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">提现管理</div>
        <div class="layui-card-body">
            <!-- 搜索表单 -->
            <form class="layui-form layui-form-pane" action="" method="get">
                <div class="layui-form-item">
                    <div class="layui-inline">
                        <label class="layui-form-label">关键词</label>
                        <div class="layui-input-inline">
                            <input type="text" name="keyword" value="<?php print htmlspecialchars($keyword); ?>" placeholder="昵称/手机号" autocomplete="off" class="layui-input">
                        </div>
                    </div>
                    <div class="layui-inline">
                        <label class="layui-form-label">状态</label>
                        <div class="layui-input-inline">
                            <select name="status">
                                <option value="-1" <?php print $status == -1 ? 'selected' : ''; ?>>全部</option>
                                <option value="0" <?php print $status == 0 ? 'selected' : ''; ?>>待审核</option>
                                <option value="1" <?php print $status == 1 ? 'selected' : ''; ?>>已通过</option>
                                <option value="2" <?php print $status == 2 ? 'selected' : ''; ?>>已拒绝</option>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button type="submit" class="layui-btn layui-btn-normal"><i class="layui-icon layui-icon-search"></i> 搜索</button>
                        <a href="withdraw_list.php" class="layui-btn layui-btn-primary">重置</a>
                    </div>
                </div>
            </form>

            <!-- 数据表格 -->
            <table class="layui-table">
                <thead>
                    <tr>
                        <th width="60">ID</th>
                        <th width="80">用户</th>
                        <th>用户信息</th>
                        <th>提现金额</th>
                        <th>到账金额</th>
                        <th>提现方式</th>
                        <th width="80">状态</th>
                        <th width="150">申请时间</th>
                        <th width="120">操作</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($withdrawals as $withdraw): ?>
                    <tr>
                        <td><?php print $withdraw['id']; ?></td>
                        <td>
                            <img src="<?php print $withdraw['avatar'] ?: '/uploads/avatar/default.png'; ?>" style="width: 50px; height: 50px; border-radius: 50%;" onerror="this.src='/uploads/avatar/default.png'">
                        </td>
                        <td>
                            <p><strong><?php print $withdraw['nickname'] ?: '未知用户'; ?></strong></p>
                            <p><?php print $withdraw['phone'] ?: ''; ?></p>
                        </td>
                        <td>
                            <span style="color: #f44336; font-weight: bold;">¥<?php print number_format($withdraw['amount'], 2); ?></span>
                        </td>
                        <td>¥<?php print number_format($withdraw['real_amount'], 2); ?></td>
                        <td>
                            <?php if ($withdraw['type'] == 1): ?>
                                <p>支付宝</p>
                                <p><?php print $withdraw['account']; ?></p>
                            <?php else: ?>
                                <p>微信</p>
                                <p><?php print $withdraw['account']; ?></p>
                            <?php endif; ?>
                        </td>
                        <td>
                            <span class="layui-badge <?php print $withdraw_status[$withdraw['status']]['class']; ?>">
                                <?php print $withdraw_status[$withdraw['status']]['text']; ?>
                            </span>
                        </td>
                        <td><?php print date('Y-m-d H:i', strtotime($withdraw['create_time'])); ?></td>
                        <td>
                            <?php if ($withdraw['status'] == 0): ?>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-success" onclick="approveWithdraw(<?php print $withdraw['id']; ?>)">通过</button>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-danger" onclick="rejectWithdraw(<?php print $withdraw['id']; ?>)">拒绝</button>
                            <?php elseif ($withdraw['status'] == 2): ?>
                            <span class="layui-text"><?php print $withdraw['reject_reason']; ?></span>
                            <?php else: ?>
                            <span class="layui-text"><?php print date('Y-m-d H:i', strtotime($withdraw['handle_time'])); ?></span>
                            <?php endif; ?>
                        </td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>

            <!-- 分页 -->
            <div class="layui-box layui-laypage layui-laypage-default">
                <?php
                $url = "withdraw_list.php?keyword=" . urlencode($keyword) . "&status={$status}";
                print generatePagination($total, $page, $limit, $url);
                ?>
            </div>
        </div>
    </div>
</div>

<!-- 拒绝弹窗 -->
<div id="rejectModal" style="display: none; padding: 20px;">
    <form class="layui-form" id="rejectForm">
        <input type="hidden" name="id" id="reject_id" value="0">
        <input type="hidden" name="action" value="reject">
        
        <div class="layui-form-item">
            <label class="layui-form-label">拒绝原因</label>
            <div class="layui-input-block">
                <textarea name="reason" id="reject_reason" placeholder="请输入拒绝原因" class="layui-textarea"></textarea>
            </div>
        </div>
    </form>
</div>

<script src="../public/layui/layui.js"></script>
<script>
layui.use(['layer'], function(){
    var layer = layui.layer;

    window.approveWithdraw = function(id) {
        layer.confirm('确定要通过该提现申请吗？', function(index) {
            var formData = new FormData();
            formData.append('action', 'approve');
            formData.append('id', id);
            
            fetch('withdraw_list.php', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.code == 0) {
                    layer.msg('已通过', {icon: 1});
                    setTimeout(function() { location.reload(); }, 1000);
                } else {
                    layer.msg(data.msg || '操作失败', {icon: 2});
                }
            });
            layer.close(index);
        });
    };

    window.rejectWithdraw = function(id) {
        document.getElementById('reject_id').value = id;
        document.getElementById('reject_reason').value = '';
        
        layer.open({
            type: 1,
            title: '拒绝提现',
            area: ['500px', '250px'],
            content: document.getElementById('rejectModal'),
            btn: ['确认拒绝', '取消'],
            yes: function(index) {
                var formData = new FormData(document.getElementById('rejectForm'));
                fetch('withdraw_list.php', {
                    method: 'POST',
                    body: formData
                })
                .then(res => res.json())
                .then(data => {
                    if (data.code == 0) {
                        layer.msg('已拒绝', {icon: 1});
                        setTimeout(function() { location.reload(); }, 1000);
                    } else {
                        layer.msg(data.msg || '操作失败', {icon: 2});
                    }
                });
            }
        });
    };
});
</script>

</body>
</html>
