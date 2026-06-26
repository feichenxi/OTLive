<?php
/**
 * EXHome 聊天管理 - 会话列表
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
        case 'delete':
            $id = intval($_POST['id'] ?? 0);
            if ($id <= 0) jsonResponse(1, '参数错误');
            
            $sql = "DELETE FROM chat_messages WHERE id = {$id}";
            if (mysqli_query($db, $sql)) {
                jsonResponse(0, '删除成功');
            } else {
                jsonResponse(1, '删除失败: ' . mysqli_error($db));
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

if ($keyword) {
    $keyword_escaped = mysqli_real_escape_string($db, $keyword);
    $where .= " AND (u1.nickname LIKE '%{$keyword_escaped}%' OR u2.nickname LIKE '%{$keyword_escaped}%' OR c.content LIKE '%{$keyword_escaped}%')";
}

// 获取总记录数
$sql = "SELECT COUNT(*) as count FROM chat_messages c 
        LEFT JOIN users u1 ON c.from_user_id = u1.id 
        LEFT JOIN users u2 ON c.to_user_id = u2.id {$where}";
$result = mysqli_query($db, $sql);
$total = mysqli_fetch_assoc($result)['count'];

// 获取聊天记录列表
$sql = "SELECT c.*, 
        u1.nickname as from_nickname, u1.avatar as from_avatar,
        u2.nickname as to_nickname, u2.avatar as to_avatar
        FROM chat_messages c 
        LEFT JOIN users u1 ON c.from_user_id = u1.id 
        LEFT JOIN users u2 ON c.to_user_id = u2.id 
        {$where} ORDER BY c.create_time DESC LIMIT {$offset}, {$limit}";
$result = mysqli_query($db, $sql);
$messages = array();
while ($row = mysqli_fetch_assoc($result)) {
    $messages[] = $row;
}

$setting = getSetting();
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>聊天管理 - <?php print $setting['app_name']; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">聊天管理</div>
        <div class="layui-card-body">
            <!-- 搜索表单 -->
            <form class="layui-form layui-form-pane" action="" method="get">
                <div class="layui-form-item">
                    <div class="layui-inline">
                        <label class="layui-form-label">关键词</label>
                        <div class="layui-input-inline">
                            <input type="text" name="keyword" value="<?php print htmlspecialchars($keyword); ?>" placeholder="昵称/消息内容" autocomplete="off" class="layui-input">
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button type="submit" class="layui-btn layui-btn-normal"><i class="layui-icon layui-icon-search"></i> 搜索</button>
                        <a href="chat_list.php" class="layui-btn layui-btn-primary">重置</a>
                    </div>
                </div>
            </form>

            <!-- 数据表格 -->
            <table class="layui-table">
                <thead>
                    <tr>
                        <th width="60">ID</th>
                        <th>发送者</th>
                        <th>接收者</th>
                        <th>消息内容</th>
                        <th width="80">类型</th>
                        <th width="80">状态</th>
                        <th width="150">时间</th>
                        <th width="80">操作</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($messages as $msg): ?>
                    <tr>
                        <td><?php print $msg['id']; ?></td>
                        <td>
                            <div style="display: flex; align-items: center;">
                                <img src="<?php print $msg['from_avatar'] ?: '/uploads/avatar/default.png'; ?>" style="width: 40px; height: 40px; border-radius: 50%; margin-right: 10px;" onerror="this.src='/uploads/avatar/default.png'">
                                <span><?php print $msg['from_nickname'] ?: '未知用户'; ?></span>
                            </div>
                        </td>
                        <td>
                            <div style="display: flex; align-items: center;">
                                <img src="<?php print $msg['to_avatar'] ?: '/uploads/avatar/default.png'; ?>" style="width: 40px; height: 40px; border-radius: 50%; margin-right: 10px;" onerror="this.src='/uploads/avatar/default.png'">
                                <span><?php print $msg['to_nickname'] ?: '未知用户'; ?></span>
                            </div>
                        </td>
                        <td>
                            <?php if ($msg['type'] == 1): ?>
                                <?php print htmlspecialchars($msg['content']); ?>
                            <?php elseif ($msg['type'] == 2): ?>
                                <span class="layui-badge layui-bg-blue">[图片]</span>
                            <?php elseif ($msg['type'] == 3): ?>
                                <span class="layui-badge layui-bg-green">[语音]</span>
                            <?php else: ?>
                                <span class="layui-badge layui-bg-gray">[其他]</span>
                            <?php endif; ?>
                        </td>
                        <td>
                            <?php if ($msg['type'] == 1): ?>
                                <span class="layui-badge layui-bg-blue">文本</span>
                            <?php elseif ($msg['type'] == 2): ?>
                                <span class="layui-badge layui-bg-green">图片</span>
                            <?php elseif ($msg['type'] == 3): ?>
                                <span class="layui-badge layui-bg-orange">语音</span>
                            <?php else: ?>
                                <span class="layui-badge layui-bg-gray">其他</span>
                            <?php endif; ?>
                        </td>
                        <td>
                            <?php if ($msg['is_read'] == 1): ?>
                                <span class="layui-badge layui-bg-gray">已读</span>
                            <?php else: ?>
                                <span class="layui-badge layui-bg-orange">未读</span>
                            <?php endif; ?>
                        </td>
                        <td><?php print date('Y-m-d H:i', strtotime($msg['create_time'])); ?></td>
                        <td>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-danger" onclick="deleteMessage(<?php print $msg['id']; ?>)">删除</button>
                        </td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>

            <!-- 分页 -->
            <div class="layui-box layui-laypage layui-laypage-default">
                <?php
                $url = "chat_list.php?keyword=" . urlencode($keyword);
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

    window.deleteMessage = function(id) {
        layer.confirm('确定要删除该消息吗？', function(index) {
            var formData = new FormData();
            formData.append('action', 'delete');
            formData.append('id', id);
            
            fetch('chat_list.php', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.code == 0) {
                    layer.msg('删除成功', {icon: 1});
                    setTimeout(function() { location.reload(); }, 1000);
                } else {
                    layer.msg(data.msg || '删除失败', {icon: 2});
                }
            });
            layer.close(index);
        });
    };
});
</script>

</body>
</html>
