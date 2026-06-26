<?php
/**
 * EXHome 财务管理 - 财务明细
 */
$login = "yes";
require("../data/class.php");
require("../data/config.php");

if (!checkAdminLogin()) {
    header("Location: ../login.php");
    exit;
}

$db = getDbConnection();

// 获取分页参数
$pageParams = getPageParams();
$page = $pageParams['page'];
$limit = $pageParams['limit'];
$offset = $pageParams['offset'];

// 搜索条件
$where = "WHERE 1=1";
$keyword = isset($_GET['keyword']) ? trim($_GET['keyword']) : '';
$type = isset($_GET['type']) ? intval($_GET['type']) : 0;

if ($keyword) {
    $keyword_escaped = mysqli_real_escape_string($db, $keyword);
    $where .= " AND (u.nickname LIKE '%{$keyword_escaped}%' OR u.phone LIKE '%{$keyword_escaped}%')";
}

if ($type > 0) {
    $where .= " AND w.type = {$type}";
}

// 获取总记录数
$sql = "SELECT COUNT(*) as count FROM wallet_logs w LEFT JOIN users u ON w.user_id = u.id {$where}";
$result = mysqli_query($db, $sql);
$total = mysqli_fetch_assoc($result)['count'];

// 获取财务明细列表
$sql = "SELECT w.*, u.nickname, u.phone, u.avatar 
        FROM wallet_logs w 
        LEFT JOIN users u ON w.user_id = u.id 
        {$where} ORDER BY w.create_time DESC LIMIT {$offset}, {$limit}";
$result = mysqli_query($db, $sql);
$logs = array();
while ($row = mysqli_fetch_assoc($result)) {
    $logs[] = $row;
}

$log_types = array(
    1 => array('text' => '充值', 'class' => 'layui-bg-green'),
    2 => array('text' => '消费', 'class' => 'layui-bg-blue'),
    3 => array('text' => '提现', 'class' => 'layui-bg-orange'),
    4 => array('text' => '退款', 'class' => 'layui-bg-cyan'),
    5 => array('text' => '收入', 'class' => 'layui-bg-purple'),
);

// 统计
$sql = "SELECT 
        SUM(CASE WHEN type = 1 THEN amount ELSE 0 END) as total_recharge,
        SUM(CASE WHEN type = 2 THEN amount ELSE 0 END) as total_consume,
        SUM(CASE WHEN type = 3 THEN amount ELSE 0 END) as total_withdraw,
        SUM(CASE WHEN type = 5 THEN amount ELSE 0 END) as total_income
        FROM wallet_logs";
$result = mysqli_query($db, $sql);
$stats = mysqli_fetch_assoc($result);

$setting = getSetting();
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>财务管理 - <?php print $setting['app_name']; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">财务统计</div>
        <div class="layui-card-body">
            <div class="layui-row layui-col-space15">
                <div class="layui-col-md3">
                    <div class="layui-card" style="background: #f0f9eb;">
                        <div class="layui-card-body" style="text-align: center;">
                            <h3 style="color: #67c23a;">总充值</h3>
                            <p style="font-size: 24px; color: #67c23a; margin-top: 10px;">¥<?php print number_format($stats['total_recharge'] ?? 0, 2); ?></p>
                        </div>
                    </div>
                </div>
                <div class="layui-col-md3">
                    <div class="layui-card" style="background: #f4f4f5;">
                        <div class="layui-card-body" style="text-align: center;">
                            <h3 style="color: #909399;">总消费</h3>
                            <p style="font-size: 24px; color: #909399; margin-top: 10px;">¥<?php print number_format($stats['total_consume'] ?? 0, 2); ?></p>
                        </div>
                    </div>
                </div>
                <div class="layui-col-md3">
                    <div class="layui-card" style="background: #fdf6ec;">
                        <div class="layui-card-body" style="text-align: center;">
                            <h3 style="color: #e6a23c;">总提现</h3>
                            <p style="font-size: 24px; color: #e6a23c; margin-top: 10px;">¥<?php print number_format($stats['total_withdraw'] ?? 0, 2); ?></p>
                        </div>
                    </div>
                </div>
                <div class="layui-col-md3">
                    <div class="layui-card" style="background: #ecf5ff;">
                        <div class="layui-card-body" style="text-align: center;">
                            <h3 style="color: #409eff;">平台收入</h3>
                            <p style="font-size: 24px; color: #409eff; margin-top: 10px;">¥<?php print number_format($stats['total_income'] ?? 0, 2); ?></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="layui-card">
        <div class="layui-card-header">财务明细</div>
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
                        <label class="layui-form-label">类型</label>
                        <div class="layui-input-inline">
                            <select name="type">
                                <option value="0" <?php print $type == 0 ? 'selected' : ''; ?>>全部</option>
                                <option value="1" <?php print $type == 1 ? 'selected' : ''; ?>>充值</option>
                                <option value="2" <?php print $type == 2 ? 'selected' : ''; ?>>消费</option>
                                <option value="3" <?php print $type == 3 ? 'selected' : ''; ?>>提现</option>
                                <option value="4" <?php print $type == 4 ? 'selected' : ''; ?>>退款</option>
                                <option value="5" <?php print $type == 5 ? 'selected' : ''; ?>>收入</option>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button type="submit" class="layui-btn layui-btn-normal"><i class="layui-icon layui-icon-search"></i> 搜索</button>
                        <a href="financial_list.php" class="layui-btn layui-btn-primary">重置</a>
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
                        <th>类型</th>
                        <th>金额</th>
                        <th>余额变动</th>
                        <th>备注</th>
                        <th width="150">时间</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($logs as $log): ?>
                    <tr>
                        <td><?php print $log['id']; ?></td>
                        <td>
                            <img src="<?php print $log['avatar'] ?: '/uploads/avatar/default.png'; ?>" style="width: 50px; height: 50px; border-radius: 50%;" onerror="this.src='/uploads/avatar/default.png'">
                        </td>
                        <td>
                            <p><strong><?php print $log['nickname'] ?: '未知用户'; ?></strong></p>
                            <p><?php print $log['phone'] ?: ''; ?></p>
                        </td>
                        <td>
                            <span class="layui-badge <?php print $log_types[$log['type']]['class']; ?>">
                                <?php print $log_types[$log['type']]['text']; ?>
                            </span>
                        </td>
                        <td>
                            <span style="color: <?php print $log['amount'] >= 0 ? '#67c23a' : '#f56c6c'; ?>; font-weight: bold;">
                                <?php print $log['amount'] >= 0 ? '+' : ''; ?>¥<?php print number_format($log['amount'], 2); ?>
                            </span>
                        </td>
                        <td>¥<?php print number_format($log['balance'], 2); ?></td>
                        <td><?php print $log['remark']; ?></td>
                        <td><?php print date('Y-m-d H:i', strtotime($log['create_time'])); ?></td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>

            <!-- 分页 -->
            <div class="layui-box layui-laypage layui-laypage-default">
                <?php
                $url = "financial_list.php?keyword=" . urlencode($keyword) . "&type={$type}";
                print generatePagination($total, $page, $limit, $url);
                ?>
            </div>
        </div>
    </div>
</div>

<script src="../public/layui/layui.js"></script>
<script>
layui.use(['layer'], function(){
    var layer = layui.layer;
});
</script>

</body>
</html>
