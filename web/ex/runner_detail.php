<?php
/**
 * EXHome 骑手管理 - 骑手认证详情
 */
$login = "yes";
require("../data/class.php");
require("../data/config.php");

if (!checkAdminLogin()) {
    header("Location: ../login.php");
    exit;
}

$db = getDbConnection();

$user_id = intval($_GET['user_id'] ?? 0);
if ($user_id <= 0) {
    echo '<div style="padding: 20px; text-align: center;">参数错误</div>';
    exit;
}

// 获取骑手详细信息
$sql = "SELECT u.*, 
        rc.work_city, rc.work_district, rc.vehicle_type,
        rc.id_card_front, rc.id_card_back, rc.id_card_hand,
        rc.health_cert, rc.status as cert_status, rc.reject_reason, 
        rc.audit_time, rc.create_time as apply_time,
        a.name as audit_admin_name
        FROM users u 
        LEFT JOIN runner_cert rc ON u.id = rc.user_id
        LEFT JOIN admin a ON rc.audit_admin_id = a.id
        WHERE u.id = {$user_id} AND u.is_runner = 1";
$result = mysqli_query($db, $sql);
$runner = mysqli_fetch_assoc($result);

if (!$runner) {
    echo '<div style="padding: 20px; text-align: center;">骑手不存在</div>';
    exit;
}

// 获取骑手订单统计
$sql = "SELECT 
        COUNT(*) as total_orders,
        SUM(CASE WHEN status = 4 THEN 1 ELSE 0 END) as completed_orders,
        SUM(CASE WHEN status = 5 THEN 1 ELSE 0 END) as cancelled_orders,
        SUM(CASE WHEN status IN (2, 3) THEN 1 ELSE 0 END) as ongoing_orders,
        SUM(rider_income) as total_income
        FROM orders_pickup 
        WHERE rider_id = {$user_id}";
$result = mysqli_query($db, $sql);
$order_stats = mysqli_fetch_assoc($result);

$vehicle_types = array(
    'electric' => '电动车',
    'motorcycle' => '摩托车',
    'car' => '汽车',
    'bicycle' => '自行车'
);

$status_text = array(
    0 => array('text' => '审核中', 'class' => 'layui-bg-orange'),
    1 => array('text' => '已通过', 'class' => 'layui-bg-green'),
    2 => array('text' => '已拒绝', 'class' => 'layui-bg-red'),
    3 => array('text' => '已禁用', 'class' => 'layui-bg-gray'),
);

$setting = getSetting();
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>骑手认证详情 - <?php print $setting['app_name']; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
    <style>
        .info-card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.05); }
        .card-title { font-size: 18px; font-weight: bold; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }
        .info-row { display: flex; margin-bottom: 15px; }
        .info-label { width: 100px; color: #666; flex-shrink: 0; }
        .info-value { flex: 1; color: #333; font-weight: 500; }
        .cert-image { width: 200px; height: 130px; object-fit: cover; border-radius: 8px; cursor: pointer; margin-right: 15px; border: 1px solid #e8e8e8; }
        .cert-image:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; padding: 20px; border-radius: 8px; text-align: center; }
        .stat-number { font-size: 32px; font-weight: bold; margin: 10px 0; }
        .stat-label { font-size: 14px; opacity: 0.9; }
        .audit-info { background: #f6ffed; border: 1px solid #b7eb8f; padding: 15px; border-radius: 8px; margin-top: 15px; }
        .audit-info.rejected { background: #fff2f0; border-color: #ffccc7; }
        .user-avatar { width: 100px; height: 100px; border-radius: 50%; object-fit: cover; border: 3px solid #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    </style>
</head>
<body style="background: #f5f5f5; padding: 20px;">

<div class="layui-fluid">
    <!-- 用户信息卡片 -->
    <div class="info-card">
        <div class="layui-row layui-col-space20">
            <div class="layui-col-md2" style="text-align: center;">
                <img src="<?php print $runner['avatar'] ?: '/uploads/avatar/default.png'; ?>" class="user-avatar" onerror="this.src='/uploads/avatar/default.png'">
                <p style="margin-top: 10px;">
                    <span class="layui-badge <?php print $status_text[$runner['runner_status']]['class']; ?>">
                        <?php print $status_text[$runner['runner_status']]['text']; ?>
                    </span>
                </p>
            </div>
            <div class="layui-col-md5">
                <div class="card-title">基本信息</div>
                <div class="info-row">
                    <div class="info-label">用户ID</div>
                    <div class="info-value"><?php print $runner['id']; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">昵称</div>
                    <div class="info-value"><?php print $runner['nickname'] ?: '未设置'; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">手机号</div>
                    <div class="info-value"><?php print $runner['phone'] ?: '未绑定'; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">注册时间</div>
                    <div class="info-value"><?php print $runner['create_time']; ?></div>
                </div>
            </div>
            <div class="layui-col-md5">
                <div class="card-title">账户信息</div>
                <div class="info-row">
                    <div class="info-label">账户余额</div>
                    <div class="info-value" style="color: #f44336; font-size: 20px;">¥<?php print number_format($runner['balance'], 2); ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">积分</div>
                    <div class="info-value"><?php print $runner['points']; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">性别</div>
                    <div class="info-value"><?php print $runner['gender'] == 1 ? '男' : ($runner['gender'] == 2 ? '女' : '未知'); ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">最后登录</div>
                    <div class="info-value"><?php print $runner['login_time'] ?: '未登录'; ?></div>
                </div>
            </div>
        </div>
    </div>

    <!-- 统计卡片 -->
    <div class="layui-row layui-col-space15" style="margin-bottom: 20px;">
        <div class="layui-col-md3">
            <div class="stat-card">
                <div class="stat-label">总接单数</div>
                <div class="stat-number"><?php print $order_stats['total_orders'] ?? 0; ?></div>
            </div>
        </div>
        <div class="layui-col-md3">
            <div class="stat-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                <div class="stat-label">已完成</div>
                <div class="stat-number"><?php print $order_stats['completed_orders'] ?? 0; ?></div>
            </div>
        </div>
        <div class="layui-col-md3">
            <div class="stat-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                <div class="stat-label">进行中</div>
                <div class="stat-number"><?php print $order_stats['ongoing_orders'] ?? 0; ?></div>
            </div>
        </div>
        <div class="layui-col-md3">
            <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <div class="stat-label">总收入</div>
                <div class="stat-number">¥<?php print number_format($order_stats['total_income'] ?? 0, 2); ?></div>
            </div>
        </div>
    </div>

    <div class="layui-row layui-col-space20">
        <!-- 实名认证信息 -->
        <div class="layui-col-md6">
            <div class="info-card">
                <div class="card-title">实名认证信息</div>
                <div class="info-row">
                    <div class="info-label">真实姓名</div>
                    <div class="info-value"><?php print $runner['real_name'] ?: '未填写'; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">身份证号</div>
                    <div class="info-value"><?php print $runner['id_card'] ?: '未填写'; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">申请时间</div>
                    <div class="info-value"><?php print $runner['apply_time'] ?: '-'; ?></div>
                </div>
                
                <?php if ($runner['id_card_front'] || $runner['id_card_back'] || $runner['id_card_hand']): ?>
                <div style="margin-top: 20px;">
                    <div class="info-label" style="margin-bottom: 10px;">证件照片</div>
                    <div>
                        <?php if ($runner['id_card_front']): ?>
                        <img src="<?php print $runner['id_card_front']; ?>" class="cert-image" onclick="previewImage('<?php print $runner['id_card_front']; ?>')" title="身份证正面">
                        <?php endif; ?>
                        <?php if ($runner['id_card_back']): ?>
                        <img src="<?php print $runner['id_card_back']; ?>" class="cert-image" onclick="previewImage('<?php print $runner['id_card_back']; ?>')" title="身份证反面">
                        <?php endif; ?>
                        <?php if ($runner['id_card_hand']): ?>
                        <img src="<?php print $runner['id_card_hand']; ?>" class="cert-image" onclick="previewImage('<?php print $runner['id_card_hand']; ?>')" title="手持身份证">
                        <?php endif; ?>
                    </div>
                </div>
                <?php endif; ?>
                
                <?php if ($runner['health_cert']): ?>
                <div style="margin-top: 20px;">
                    <div class="info-label" style="margin-bottom: 10px;">健康证</div>
                    <div>
                        <img src="<?php print $runner['health_cert']; ?>" class="cert-image" onclick="previewImage('<?php print $runner['health_cert']; ?>')" title="健康证">
                    </div>
                </div>
                <?php endif; ?>
            </div>
        </div>

        <!-- 工作信息 -->
        <div class="layui-col-md6">
            <div class="info-card">
                <div class="card-title">工作信息</div>
                <div class="info-row">
                    <div class="info-label">工作城市</div>
                    <div class="info-value"><?php print $runner['work_city'] ?: '未填写'; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">工作区域</div>
                    <div class="info-value"><?php print $runner['work_district'] ?: '未填写'; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">交通工具</div>
                    <div class="info-value"><?php print $vehicle_types[$runner['vehicle_type']] ?? $runner['vehicle_type'] ?? '未选择'; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">紧急联系人</div>
                    <div class="info-value"><?php print $runner['emergency_contact'] ?: '未填写'; ?></div>
                </div>
                <div class="info-row">
                    <div class="info-label">紧急电话</div>
                    <div class="info-value"><?php print $runner['emergency_phone'] ?: '未填写'; ?></div>
                </div>
            </div>

            <!-- 审核信息 -->
            <?php if ($runner['audit_time']): ?>
            <div class="info-card">
                <div class="card-title">审核记录</div>
                <div class="audit-info <?php print $runner['cert_status'] == 2 ? 'rejected' : ''; ?>">
                    <div class="info-row">
                        <div class="info-label">审核状态</div>
                        <div class="info-value">
                            <span class="layui-badge <?php print $status_text[$runner['cert_status']]['class']; ?>">
                                <?php print $status_text[$runner['cert_status']]['text']; ?>
                            </span>
                        </div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">审核时间</div>
                        <div class="info-value"><?php print $runner['audit_time']; ?></div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">审核人</div>
                        <div class="info-value"><?php print $runner['audit_admin_name'] ?: '未知'; ?></div>
                    </div>
                    <?php if ($runner['reject_reason']): ?>
                    <div class="info-row">
                        <div class="info-label">拒绝原因</div>
                        <div class="info-value" style="color: #f44336;"><?php print $runner['reject_reason']; ?></div>
                    </div>
                    <?php endif; ?>
                </div>
            </div>
            <?php endif; ?>
        </div>
    </div>

    <!-- 操作按钮 -->
    <div class="info-card" style="text-align: center;">
        <?php if ($runner['runner_status'] == 0): ?>
        <button type="button" class="layui-btn layui-btn-lg layui-btn-success" onclick="audit(1)">审核通过</button>
        <button type="button" class="layui-btn layui-btn-lg layui-btn-danger" onclick="audit(2)">审核拒绝</button>
        <?php elseif ($runner['runner_status'] == 1): ?>
        <button type="button" class="layui-btn layui-btn-lg layui-btn-danger" onclick="audit(3)">禁用骑手</button>
        <?php else: ?>
        <button type="button" class="layui-btn layui-btn-lg layui-btn-success" onclick="audit(1)">启用骑手</button>
        <?php endif; ?>
    </div>
</div>

<!-- 审核弹窗 -->
<div id="auditModal" style="display: none; padding: 20px;">
    <form class="layui-form" id="auditForm">
        <input type="hidden" name="user_id" id="audit_user_id" value="<?php print $user_id; ?>">
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
layui.use(['layer'], function(){
    var layer = layui.layer;

    // 预览图片
    window.previewImage = function(src) {
        layer.photos({
            photos: {
                title: '证件预览',
                data: [{ src: src }]
            },
            shade: 0.5,
            anim: 5
        });
    };

    // 审核操作
    window.audit = function(status) {
        document.getElementById('audit_status').value = status;
        
        var title = '';
        var confirmText = '';
        
        switch(status) {
            case 1:
                title = '审核通过';
                confirmText = '确定要通过该骑手的认证申请吗？';
                document.getElementById('rejectReasonBox').style.display = 'none';
                break;
            case 2:
                title = '审核拒绝';
                confirmText = '确定要拒绝该骑手的认证申请吗？';
                document.getElementById('rejectReasonBox').style.display = 'block';
                break;
            case 3:
                title = '禁用骑手';
                confirmText = '确定要禁用该骑手吗？禁用后该骑手将无法接单。';
                document.getElementById('rejectReasonBox').style.display = 'none';
                break;
        }
        
        document.querySelector('#confirmText p').textContent = confirmText;
        
        layer.open({
            type: 1,
            title: title,
            area: ['500px', status == 2 ? '350px' : '250px'],
            content: document.getElementById('auditModal'),
            btn: ['确定', '取消'],
            yes: function(index) {
                if (status == 2) {
                    var reason = document.getElementById('reject_reason').value.trim();
                    if (!reason) {
                        layer.msg('请输入拒绝原因', {icon: 2});
                        return;
                    }
                }
                
                var formData = new FormData(document.getElementById('auditForm'));
                formData.append('action', 'audit');
                
                fetch('runner_list.php', {
                    method: 'POST',
                    body: formData
                })
                .then(res => res.json())
                .then(data => {
                    if (data.code == 0) {
                        layer.msg('操作成功', {icon: 1});
                        setTimeout(function() { parent.location.reload(); }, 1000);
                    } else {
                        layer.msg(data.msg || '操作失败', {icon: 2});
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
