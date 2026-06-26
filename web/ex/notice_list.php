<?php
/**
 * EXHome 公告管理 - 公告列表
 */
$login = "yes";
require("../data/class.php");
require("../data/config.php");

// 检查登录
if (!checkAdminLogin()) {
    header("Location: ../login.php");
    exit;
}

$db = getDbConnection();

// 处理AJAX请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];
    
    switch ($action) {
        case 'save':
            $id = intval($_POST['id'] ?? 0);
            $title = trim($_POST['title'] ?? '');
            $type = intval($_POST['type'] ?? 1);
            $content = trim($_POST['content'] ?? '');
            $sort = intval($_POST['sort'] ?? 0);
            $status = intval($_POST['status'] ?? 1);
            
            if (empty($title)) {
                jsonResponse(1, '请输入公告标题');
            }
            
            $title_escaped = mysqli_real_escape_string($db, $title);
            $content_escaped = mysqli_real_escape_string($db, $content);
            
            if ($id > 0) {
                $sql = "UPDATE notices SET 
                        title = '{$title_escaped}',
                        type = {$type},
                        content = '{$content_escaped}',
                        sort = {$sort},
                        status = {$status},
                        update_time = NOW()
                        WHERE id = {$id}";
                $msg = '更新成功';
            } else {
                $sql = "INSERT INTO notices (title, type, content, sort, status, create_time, update_time) 
                        VALUES ('{$title_escaped}', {$type}, '{$content_escaped}', {$sort}, {$status}, NOW(), NOW())";
                $msg = '添加成功';
            }
            
            if (mysqli_query($db, $sql)) {
                jsonResponse(0, $msg);
            } else {
                jsonResponse(1, '操作失败: ' . mysqli_error($db));
            }
            break;
            
        case 'toggle_status':
            $id = intval($_POST['id'] ?? 0);
            $status = intval($_POST['status'] ?? 0);
            
            if ($id <= 0) jsonResponse(1, '参数错误');
            
            $sql = "UPDATE notices SET status = {$status}, update_time = NOW() WHERE id = {$id}";
            if (mysqli_query($db, $sql)) {
                jsonResponse(0, '操作成功');
            } else {
                jsonResponse(1, '操作失败: ' . mysqli_error($db));
            }
            break;
            
        case 'delete':
            $id = intval($_POST['id'] ?? 0);
            
            if ($id <= 0) jsonResponse(1, '参数错误');
            
            $sql = "DELETE FROM notices WHERE id = {$id}";
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
$status = isset($_GET['status']) ? intval($_GET['status']) : -1;

if ($keyword) {
    $keyword_escaped = mysqli_real_escape_string($db, $keyword);
    $where .= " AND title LIKE '%{$keyword_escaped}%'";
}

if ($status >= 0) {
    $where .= " AND status = {$status}";
}

// 获取总记录数
$sql = "SELECT COUNT(*) as count FROM notices {$where}";
$result = mysqli_query($db, $sql);
$total = mysqli_fetch_assoc($result)['count'];

// 获取公告列表
$sql = "SELECT * FROM notices {$where} ORDER BY sort DESC, id DESC LIMIT {$offset}, {$limit}";
$result = mysqli_query($db, $sql);
$notices = array();
while ($row = mysqli_fetch_assoc($result)) {
    $notices[] = $row;
}

$notice_types = array(1 => '系统公告', 2 => '活动通知', 3 => '规则更新');
$setting = getSetting();
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>公告管理 - <?php print $setting['app_name']; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">公告管理</div>
        <div class="layui-card-body">
            <!-- 搜索表单 -->
            <form class="layui-form layui-form-pane" action="" method="get">
                <div class="layui-form-item">
                    <div class="layui-inline">
                        <label class="layui-form-label">关键词</label>
                        <div class="layui-input-inline" style="width: 200px;">
                            <input type="text" name="keyword" value="<?php print htmlspecialchars($keyword); ?>" placeholder="公告标题" autocomplete="off" class="layui-input">
                        </div>
                    </div>
                    <div class="layui-inline">
                        <label class="layui-form-label">状态</label>
                        <div class="layui-input-inline">
                            <select name="status">
                                <option value="-1" <?php print $status == -1 ? 'selected' : ''; ?>>全部</option>
                                <option value="1" <?php print $status == 1 ? 'selected' : ''; ?>>显示</option>
                                <option value="0" <?php print $status == 0 ? 'selected' : ''; ?>>隐藏</option>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button type="submit" class="layui-btn layui-btn-normal"><i class="layui-icon layui-icon-search"></i> 搜索</button>
                        <a href="notice_list.php" class="layui-btn layui-btn-primary">重置</a>
                        <button type="button" class="layui-btn layui-btn-success" onclick="openEditModal()"><i class="layui-icon layui-icon-add-1"></i> 新增公告</button>
                    </div>
                </div>
            </form>

            <!-- 数据表格 -->
            <table class="layui-table">
                <thead>
                    <tr>
                        <th width="60">ID</th>
                        <th width="100">类型</th>
                        <th>标题</th>
                        <th width="80">排序</th>
                        <th width="80">状态</th>
                        <th width="150">创建时间</th>
                        <th width="150">操作</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($notices as $notice): ?>
                    <tr>
                        <td><?php print $notice['id']; ?></td>
                        <td><span class="layui-badge layui-bg-blue"><?php print $notice_types[$notice['type']] ?? '未知'; ?></span></td>
                        <td><?php print $notice['title']; ?></td>
                        <td><?php print $notice['sort']; ?></td>
                        <td>
                            <?php if ($notice['status'] == 1): ?>
                            <span class="layui-badge layui-bg-green">显示</span>
                            <?php else: ?>
                            <span class="layui-badge layui-bg-gray">隐藏</span>
                            <?php endif; ?>
                        </td>
                        <td><?php print date('Y-m-d H:i', strtotime($notice['create_time'])); ?></td>
                        <td>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-normal" onclick="openEditModal(<?php print $notice['id']; ?>, '<?php print addslashes($notice['title']); ?>', <?php print $notice['type']; ?>, '<?php print addslashes($notice['content']); ?>', <?php print $notice['sort']; ?>, <?php print $notice['status']; ?>)">编辑</button>
                            <?php if ($notice['status'] == 1): ?>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-danger" onclick="toggleStatus(<?php print $notice['id']; ?>, 0)">隐藏</button>
                            <?php else: ?>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-success" onclick="toggleStatus(<?php print $notice['id']; ?>, 1)">显示</button>
                            <?php endif; ?>
                            <button type="button" class="layui-btn layui-btn-xs layui-btn-danger" onclick="deleteNotice(<?php print $notice['id']; ?>)">删除</button>
                        </td>
                    </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>

            <!-- 分页 -->
            <div class="layui-box layui-laypage layui-laypage-default">
                <?php
                $url = "notice_list.php?keyword=" . urlencode($keyword) . "&status={$status}";
                print generatePagination($total, $page, $limit, $url);
                ?>
            </div>
        </div>
    </div>
</div>

<!-- 编辑弹窗 -->
<div id="editModal" style="display: none; padding: 20px;">
    <form class="layui-form" id="editForm">
        <input type="hidden" name="id" id="edit_id" value="0">
        <input type="hidden" name="action" value="save">
        
        <div class="layui-form-item">
            <label class="layui-form-label">公告标题</label>
            <div class="layui-input-block">
                <input type="text" name="title" id="edit_title" required lay-verify="required" placeholder="请输入公告标题" autocomplete="off" class="layui-input">
            </div>
        </div>
        
        <div class="layui-form-item">
            <label class="layui-form-label">公告类型</label>
            <div class="layui-input-inline">
                <select name="type" id="edit_type">
                    <option value="1">系统公告</option>
                    <option value="2">活动通知</option>
                    <option value="3">规则更新</option>
                </select>
            </div>
        </div>
        
        <div class="layui-form-item">
            <label class="layui-form-label">排序</label>
            <div class="layui-input-inline">
                <input type="number" name="sort" id="edit_sort" value="0" placeholder="数值越大越靠前" autocomplete="off" class="layui-input">
            </div>
            <div class="layui-form-mid layui-word-aux">数值越大排序越靠前</div>
        </div>
        
        <div class="layui-form-item">
            <label class="layui-form-label">状态</label>
            <div class="layui-input-block">
                <input type="radio" name="status" value="1" title="显示" checked>
                <input type="radio" name="status" value="0" title="隐藏">
            </div>
        </div>
        
        <div class="layui-form-item">
            <label class="layui-form-label">公告内容</label>
            <div class="layui-input-block">
                <textarea name="content" id="edit_content" placeholder="请输入公告内容" class="layui-textarea" rows="6"></textarea>
            </div>
        </div>
    </form>
</div>

<script src="../public/layui/layui.js"></script>
<script>
layui.use(['layer', 'form'], function(){
    var layer = layui.layer;
    var form = layui.form;

    window.openEditModal = function(id, title, type, content, sort, status) {
        id = id || 0;
        document.getElementById('edit_id').value = id;
        document.getElementById('edit_title').value = title || '';
        document.getElementById('edit_type').value = type || 1;
        document.getElementById('edit_content').value = content || '';
        document.getElementById('edit_sort').value = sort || 0;
        
        var statusRadios = document.getElementsByName('status');
        for (var i = 0; i < statusRadios.length; i++) {
            statusRadios[i].checked = (statusRadios[i].value == (status || 1));
        }
        form.render('radio');
        form.render('select');
        
        layer.open({
            type: 1,
            title: id > 0 ? '编辑公告' : '新增公告',
            area: ['600px', '500px'],
            content: document.getElementById('editModal'),
            btn: ['保存', '取消'],
            yes: function(index) {
                var formData = new FormData(document.getElementById('editForm'));
                fetch('notice_list.php', {
                    method: 'POST',
                    body: formData
                })
                .then(res => res.json())
                .then(data => {
                    if (data.code == 0) {
                        layer.msg('保存成功', {icon: 1});
                        setTimeout(function() { location.reload(); }, 1000);
                    } else {
                        layer.msg(data.msg || '保存失败', {icon: 2});
                    }
                });
            }
        });
    };

    window.toggleStatus = function(id, status) {
        var msg = status == 1 ? '确定要显示该公告吗？' : '确定要隐藏该公告吗？';
        layer.confirm(msg, function(index) {
            var formData = new FormData();
            formData.append('action', 'toggle_status');
            formData.append('id', id);
            formData.append('status', status);
            
            fetch('notice_list.php', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.code == 0) {
                    layer.msg('操作成功', {icon: 1});
                    setTimeout(function() { location.reload(); }, 1000);
                } else {
                    layer.msg(data.msg || '操作失败', {icon: 2});
                }
            });
            layer.close(index);
        });
    };

    window.deleteNotice = function(id) {
        layer.confirm('确定要删除该公告吗？删除后不可恢复！', function(index) {
            var formData = new FormData();
            formData.append('action', 'delete');
            formData.append('id', id);
            
            fetch('notice_list.php', {
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
