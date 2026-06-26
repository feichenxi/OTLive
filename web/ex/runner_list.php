<?php
/**
 * EXHome 骑手管理 - 骑手列表
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
        case 'audit':
            error_log('=== 审核请求开始 ===');
            error_log('POST数据: ' . print_r($_POST, true));
            
            $user_id = intval($_POST['user_id'] ?? 0);
            $status = intval($_POST['status'] ?? 0);
            $reject_reason = trim($_POST['reject_reason'] ?? '');
            $admin_id = $_SESSION['admin_id'] ?? 0;
            
            error_log("user_id: {$user_id}, status: {$status}, admin_id: {$admin_id}");
            
            if ($user_id <= 0) {
                error_log('参数错误');
                jsonResponse(1, '参数错误');
            }
            
            // 更新用户表状态
            if ($status == 1) {
                $sql = "UPDATE users SET 
                        runner_status = {$status},
                        is_runner = 1
                        WHERE id = {$user_id}";
            } else {
                $sql = "UPDATE users SET 
                        runner_status = {$status}
                        WHERE id = {$user_id}";
            }
            
            error_log('执行SQL: ' . $sql);
            
            if (!mysqli_query($db, $sql)) {
                error_log('SQL执行失败: ' . mysqli_error($db));
                jsonResponse(1, '操作失败: ' . mysqli_error($db));
            }
            error_log('用户表更新成功，影响行数: ' . mysqli_affected_rows($db));
            
            // 更新认证表状态
            $reject_reason_escaped = mysqli_real_escape_string($db, $reject_reason);
            $sql = "UPDATE runner_cert SET 
                    status = {$status}, 
                    reject_reason = '{$reject_reason_escaped}',
                    audit_time = NOW(),
                    audit_admin_id = {$admin_id}
                    WHERE user_id = {$user_id}";
            
            error_log('更新认证表SQL: ' . $sql);
            
            mysqli_query($db, $sql);
            error_log('认证表更新成功，影响行数: ' . mysqli_affected_rows($db));
            error_log('=== 审核请求完成 ===');
            
            jsonResponse(0, '操作成功');
            break;
            
        case 'update_info':
            $user_id = intval($_POST['user_id'] ?? 0);
            $real_name = trim($_POST['real_name'] ?? '');
            $id_card = trim($_POST['id_card'] ?? '');
            $phone = trim($_POST['phone'] ?? '');
            
            if ($user_id <= 0) jsonResponse(1, '参数错误');
            
            $real_name_escaped = mysqli_real_escape_string($db, $real_name);
            $id_card_escaped = mysqli_real_escape_string($db, $id_card);
            $phone_escaped = mysqli_real_escape_string($db, $phone);
            
            $sql = "UPDATE users SET 
                    real_name = '{$real_name_escaped}', 
                    id_card = '{$id_card_escaped}',
                    phone = '{$phone_escaped}'
                    WHERE id = {$user_id}";
            if (mysqli_query($db, $sql)) {
                jsonResponse(0, '更新成功');
            } else {
                jsonResponse(1, '更新失败: ' . mysqli_error($db));
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
$where = "WHERE u.is_runner = 1";
$keyword = isset($_GET['keyword']) ? trim($_GET['keyword']) : '';
$status = isset($_GET['status']) ? intval($_GET['status']) : -1;

if ($keyword) {
    $keyword_escaped = mysqli_real_escape_string($db, $keyword);
    $where .= " AND (u.nickname LIKE '%{$keyword_escaped}%' OR u.phone LIKE '%{$keyword_escaped}%' OR u.real_name LIKE '%{$keyword_escaped}%')";
}

if ($status >= 0) {
    $where .= " AND u.runner_status = {$status}";
}

// 获取总记录数
$sql = "SELECT COUNT(*) as count FROM users u {$where}";
$result = mysqli_query($db, $sql);
$total = mysqli_fetch_assoc($result)['count'];

// 获取骑手列表（关联认证表）
$sql = "SELECT u.*, 
        rc.work_city, rc.work_district, rc.vehicle_type,
        rc.id_card_front, rc.id_card_back, rc.id_card_hand,
        rc.health_cert, rc.reject_reason, rc.audit_time,
        a.name as audit_admin_name
        FROM users u 
        LEFT JOIN runner_cert rc ON u.id = rc.user_id
        LEFT JOIN admin a ON rc.audit_admin_id = a.id
        {$where} 
        ORDER BY u.id DESC 
        LIMIT {$offset}, {$limit}";
$result = mysqli_query($db, $sql);
$runners = array();
while ($row = mysqli_fetch_assoc($result)) {
    $runners[] = $row;
}

$runner_status = array(
    0 => array('text' => '审核中', 'class' => 'layui-bg-orange'),
    1 => array('text' => '已通过', 'class' => 'layui-bg-green'),
    2 => array('text' => '已拒绝', 'class' => 'layui-bg-red'),
    3 => array('text' => '已禁用', 'class' => 'layui-bg-gray'),
);

$vehicle_types = array(
    'electric' => '电动车',
    'motorcycle' => '摩托车',
    'car' => '汽车',
    'bicycle' => '自行车'
);

$setting = getSetting();
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>骑手管理 - <?php print $setting['app_name']; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
    <style>
        .cert-image { width: 120px; height: 80px; object-fit: cover; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        .info-row { margin-bottom: 8px; }
        .info-label { color: #666; display: inline-block; width: 80px; }
        .info-value { color: #333; font-weight: 500; }
        .audit-info { background: #f5f5f5; padding: 10px; border-radius: 4px; margin-top: 10px; }
    </style>
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">骑手管理</div>
        <div class="layui-card-body">
            <!-- 统计卡片 -->
            <div class="layui-row layui-col-space15" style="margin-bottom: 20px;">
                <div class="layui-col-md3">
                    <div class="layui-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <div class="layui-card-body" style="color: #fff; padding: 20px;">
                            <h3>总骑手数</h3>
                            <p style="font-size: 32px; font-weight: bold; margin-top: 10px;"><?php print $total; ?></p>
                        </div>
                    </div>
                </div>
                <div class="layui-col-md3">
                    <div class="layui-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                        <div class="layui-card-body" style="color: #fff; padding: 20px;">
                            <h3>待审核</h3>
                            <p style="font-size: 32px; font-weight: bold; margin-top: 10px;">
                                <?php
                                $sql = "SELECT COUNT(*) as count FROM users WHERE is_runner = 1 AND runner_status = 0";
                                $result = mysqli_query($db, $sql);
                                print mysqli_fetch_assoc($result)['count'];
                                ?>
                            </p>
                        </div>
                    </div>
                </div>
                <div class="layui-col-md3">
                    <div class="layui-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                        <div class="layui-card-body" style="color: #fff; padding: 20px;">
                            <h3>已通过</h3>
                            <p style="font-size: 32px; font-weight: bold; margin-top: 10px;">
                                <?php
                                $sql = "SELECT COUNT(*) as count FROM users WHERE is_runner = 1 AND runner_status = 1";
                                $result = mysqli_query($db, $sql);
                                print mysqli_fetch_assoc($result)['count'];
                                ?>
                            </p>
                        </div>
                    </div>
                </div>
                <div class="layui-col-md3">
                    <div class="layui-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                        <div class="layui-card-body" style="color: #fff; padding: 20px;">
                            <h3>今日新增</h3>
                            <p style="font-size: 32px; font-weight: bold; margin-top: 10px;">
                                <?php
                                $sql = "SELECT COUNT(*) as count FROM users WHERE is_runner = 1 AND DATE(create_time) = CURDATE()";
                                $result = mysqli_query($db, $sql);
                                print mysqli_fetch_assoc($result)['count'];
                                ?>
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 搜索表单 -->
            <form class="layui-form layui-form-pane" action="" method="get">
                <div class="layui-form-item">
                    <div class="layui-inline">
                        <label class="layui-form-label">关键词</label>
                        <div class="layui-input-inline">
                            <input type="text" name="keyword" value="<?php print htmlspecialchars($keyword); ?>" placeholder="昵称/手机号/姓名" autocomplete="off" class="layui-input">
                        </div>
                    </div>
                    <div class="layui-inline">
                        <label class="layui-form-label">状态</label>
                        <div class="layui-input-inline">
                            <select name="status">
                                <option value="-1" <?php print $status == -1 ? 'selected' : ''; ?>>全部</option>
                                <option value="0" <?php print $status == 0 ? 'selected' : ''; ?>>审核中</option>
                                <option value="1" <?php print $status == 1 ? 'selected' : ''; ?>>已通过</option>
                                <option value="2" <?php print $status == 2 ? 'selected' : ''; ?>>已拒绝</option>
                                <option value="3" <?php print $status == 3 ? 'selected' : ''; ?>>已禁用</option>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button type="submit" class="layui-btn layui-btn-normal"><i class="layui-icon layui-icon-search"></i> 搜索</button>
                        <a href="runner_list.php" class="layui-btn layui-btn-primary">重置</a>
                    </div>
                </div>
            </form>

            <!-- 数据表格 -->
            <table class="layui-table">
                <thead>
                    <tr>
                        <th width="60">ID</th>
                        <th width="80">头像</th>
                        <th>用户信息</th>
                        <th>认证信息</th>
                        <th>工作信息</th>
                        <th width="80">状态</th>
                        <th width="150">申请时间</th>
                        <th width="200">操作</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($runners as $runner): ?>
                    <tr>
                        <td><?php print $runner['id']; ?></td>
                        <td>
                            <img src="<?php print $runner['avatar'] ?: '/uploads/avatar/default.png'; ?>" style="width: 50px; height: 50px; border-radius: 50%;" onerror="this.src='/uploads/avatar/default.png'">
                        </td>
                        <td>
                            <p><strong><?php print $runner['nickname'] ?: '未设置昵称'; ?></strong></p>
                            <p>手机号: <?php print $runner['phone'] ?: '未绑定'; ?></p>
                            <p>余额: <span style="color: #f44336;">¥<?php print number_format($runner['balance'], 2); ?></span></p>
                        </td>
                        <td>
                            <p>姓名: <?php print $runner['real_name'] ?: '未填写'; ?></p>
                            <p>身份证: <?php print $runner['id_card'] ? substr_replace($runner['id_card'], '****', 6, 8) : '-'; ?></p>
                            <?php if ($runner['id_card_front']): ?>
                            <p style="margin-top: 5px;">
                                <span class="layui-badge layui-bg-blue">已上传证件</span>
                            </p>
                            <?php endif; ?>
                        </td>
                        <td>
                            <p>城市: <?php print $runner['work_city'] ?: '-'; ?></p>
                            <p>区域: <?php print $runner['work_district'] ?: '-'; ?></p>
                            <p>交通工具: <?php print $vehicle_types[$runner['vehicle_type']] ?? $runner['vehicle_type'] ?? '-'; ?></p>
                        </td>
                        <td>
                            <span class="layui-badge <?php print $runner_status[$runner['runner_status']]['class']; ?>">
                                <?php print $runner_status[$runner['runner_status']]['text']; ?>
                            </span>
                        </td>
                        <td><?php print date('Y-m-d H:i', strtotime($runner['create_time'])); ?></td>
                        <td>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-normal" onclick="viewDetail(<?php print $runner['id']; ?>)">查看详情</button>
                            <?php if ($runner['runner_status'] == 0): ?>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-success" onclick="openAuditModal(<?php print $runner['id']; ?>, 1)">通过</button>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-danger" onclick="openAuditModal(<?php print $runner['id']; ?>, 2)">拒绝</button>
                            <?php elseif ($runner['runner_status'] == 1): ?>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-danger" onclick="openAuditModal(<?php print $runner['id']; ?>, 3)">禁用</button>
                            <?php else: ?>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-success" onclick="openAuditModal(<?php print $runner['id']; ?>, 1)">启用</button>
                            <?php endif; ?>
                        </td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>

            <!-- 分页 -->
            <div class="layui-box layui-laypage layui-laypage-default">
                <?php
                $url = "runner_list.php?keyword=" . urlencode($keyword) . "&status={$status}";
                print generatePagination($total, $page, $limit, $url);
                ?>
            </div>
        </div>
    </div>
</div>

<!-- 审核弹窗 -->
<div id="auditModal" style="display: none; padding: 20px;">
    <form class="layui-form" id="auditForm">
        <input type="hidden" name="user_id" id="audit_user_id" value="0">
        <input type="hidden" name="status" id="audit_status" value="0">
        
        <div class="layui-form-item" id="rejectReasonBox" style="display: none;">
            <label class="layui-form-label">拒绝原因</label>
            <div class="layui-input-block">
                <textarea name="reject_reason" id="reject_reason" placeholder="请输入拒绝原因" class="layui-textarea"></textarea>
            </div>
        </div>
        
        <div class="layui-form-item" id="confirmText">
            <div class="layui-input-block" style="margin-left: 0;">
                <p style="font-size: 16px; color: #333;">确定要执行此操作吗？</p>
            </div>
        </div>
    </form>
</div>

<script src="../public/layui/layui.js"></script>
<script>
layui.use(['layer', 'form', 'jquery'], function(){
    var layer = layui.layer;
    var form = layui.form;
    var $ = layui.jquery;

    // 查看详情
    window.viewDetail = function(user_id) {
        layer.open({
            type: 2,
            title: '骑手认证详情',
            area: ['800px', '90%'],
            content: 'runner_detail.php?user_id=' + user_id
        });
    };

    // 打开审核弹窗
    window.openAuditModal = function(user_id, status) {
        $('#audit_user_id').val(user_id);
        $('#audit_status').val(status);
        
        var title = '';
        var confirmText = '';
        
        switch(status) {
            case 1:
                title = '审核通过';
                confirmText = '确定要通过该骑手的认证申请吗？';
                $('#rejectReasonBox').hide();
                break;
            case 2:
                title = '审核拒绝';
                confirmText = '确定要拒绝该骑手的认证申请吗？';
                $('#rejectReasonBox').show();
                break;
            case 3:
                title = '禁用骑手';
                confirmText = '确定要禁用该骑手吗？禁用后该骑手将无法接单。';
                $('#rejectReasonBox').hide();
                break;
        }
        
        $('#confirmText p').text(confirmText);
        
        layer.open({
            type: 1,
            title: title,
            area: ['500px', status == 2 ? '350px' : '250px'],
            content: $('#auditModal'),
            btn: ['确定', '取消'],
            yes: function(index) {
                console.log('开始提交审核...');
                
                $.ajax({
                    url: 'runner_list.php',
                    type: 'POST',
                    data: $('#auditForm').serialize() + '&action=audit',
                    dataType: 'json',
                    success: function(data) {
                        console.log('响应内容:', data);
                        if (data.code == 0) {
                            layer.msg('操作成功', {icon: 1});
                            setTimeout(function() { location.reload(); }, 1000);
                        } else {
                            layer.msg(data.msg || '操作失败', {icon: 2});
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('请求失败:', error);
                        layer.msg('网络请求失败', {icon: 2});
                    }
                });
                layer.close(index);
            }
        });
    };
});
</script>

</body>
</html>
