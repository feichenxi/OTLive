<?php
require("../data/class.php");

// 处理AJAX请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];
    
    switch ($action) {
        case 'toggle_status':
            $id = intval($_POST['id'] ?? 0);
            $status = intval($_POST['status'] ?? 0);
            
            if ($id <= 0) {
                header('Content-Type: application/json');
                echo json_encode(['code' => 1, 'msg' => '参数错误']);
                exit;
            }
            
            $sql = "UPDATE users SET status = '$status' WHERE id='$id'";
            if (mysqli_query($conn, $sql)) {
                header('Content-Type: application/json');
                echo json_encode(['code' => 0, 'msg' => '操作成功']);
            } else {
                header('Content-Type: application/json');
                echo json_encode(['code' => 1, 'msg' => '操作失败: ' . mysqli_error($conn)]);
            }
            exit;
    }
}

// 数据接口
if (isset($_GET['t']) && $_GET['t'] == 'data') {
    $page = isset($_GET['page']) ? intval($_GET['page']) : 1;
    $limit = isset($_GET['limit']) ? intval($_GET['limit']) : 20;
    $offset = ($page - 1) * $limit;
    
    $where = "WHERE 1=1";
    $keyword = isset($_GET['keyword']) ? trim($_GET['keyword']) : '';
    $status = isset($_GET['status']) ? intval($_GET['status']) : -1;
    $is_runner = isset($_GET['is_runner']) ? intval($_GET['is_runner']) : -1;
    
    if ($keyword) {
        $keyword_escaped = mysqli_real_escape_string($conn, $keyword);
        $where .= " AND (nickname LIKE '%{$keyword_escaped}%' OR phone LIKE '%{$keyword_escaped}%' OR real_name LIKE '%{$keyword_escaped}%')";
    }
    
    if ($status >= 0) {
        $where .= " AND status = {$status}";
    }
    
    if ($is_runner >= 0) {
        $where .= " AND is_runner = {$is_runner}";
    }
    
    $sql_count = "SELECT COUNT(*) as count FROM users {$where}";
    $result_count = mysqli_query($conn, $sql_count);
    $count = mysqli_fetch_assoc($result_count)['count'];
    
    $sql = "SELECT * FROM users {$where} ORDER BY id DESC LIMIT {$offset}, {$limit}";
    $result = mysqli_query($conn, $sql);
    
    $data = array();
    while ($row = mysqli_fetch_assoc($result)) {
        $data[] = $row;
    }
    
    header('Content-Type: application/json;charset=utf-8');
    echo json_encode(array(
        'code' => 0,
        'msg' => '',
        'count' => $count,
        'data' => $data
    ), JSON_UNESCAPED_UNICODE);
    exit;
}
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>用户管理</title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
    <style>
        .user-avatar { width: 50px; height: 50px; border-radius: 50%; object-fit: cover; }
    </style>
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">用户管理</div>
        <div class="layui-card-body">
            <!-- 搜索表单 -->
            <div class="layui-form layui-form-pane">
                <div class="layui-form-item">
                    <div class="layui-inline">
                        <label class="layui-form-label">关键词</label>
                        <div class="layui-input-inline">
                            <input type="text" name="keyword" id="keyword-search" placeholder="昵称/手机号/姓名" autocomplete="off" class="layui-input">
                        </div>
                    </div>
                    <div class="layui-inline">
                        <label class="layui-form-label">状态</label>
                        <div class="layui-input-inline">
                            <select name="status" id="status-search">
                                <option value="-1">全部</option>
                                <option value="1">正常</option>
                                <option value="0">禁用</option>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <label class="layui-form-label">跑腿员</label>
                        <div class="layui-input-inline">
                            <select name="is_runner" id="is_runner-search">
                                <option value="-1">全部</option>
                                <option value="1">是</option>
                                <option value="0">否</option>
                            </select>
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button type="button" class="layui-btn layui-btn-normal" id="searchBtn"><i class="layui-icon layui-icon-search"></i> 搜索</button>
                        <button type="button" class="layui-btn layui-btn-primary" id="resetBtn">重置</button>
                        <button type="button" class="layui-btn layui-btn-success" id="addBtn"><i class="layui-icon layui-icon-add-1"></i> 添加用户</button>
                    </div>
                </div>
            </div>

            <!-- 数据表格 -->
            <table class="layui-table" id="data-table" lay-filter="data-table"></table>
        </div>
    </div>
</div>

<!-- 状态模板 -->
<script type="text/html" id="status-tpl">
    {{# if(d.status == 1){ }}
        <span class="layui-badge layui-bg-green">正常</span>
    {{# } else { }}
        <span class="layui-badge layui-bg-gray">禁用</span>
    {{# } }}
</script>

<!-- 跑腿员状态模板 -->
<script type="text/html" id="runner-tpl">
    {{# if(d.is_runner == 1){ }}
        {{# if(d.runner_status == 0){ }}
            <span class="layui-badge layui-bg-orange">审核中</span>
        {{# } else if(d.runner_status == 1){ }}
            <span class="layui-badge layui-bg-green">已通过</span>
        {{# } else if(d.runner_status == 2){ }}
            <span class="layui-badge layui-bg-red">已拒绝</span>
        {{# } else { }}
            <span class="layui-badge layui-bg-gray">未知</span>
        {{# } }}
    {{# } else { }}
        <span class="layui-badge layui-bg-gray">否</span>
    {{# } }}
</script>

<!-- 头像模板 -->
<script type="text/html" id="avatar-tpl">
    {{# var avatarUrl = d.avatar ? d.avatar : '/uploads/avatar/default.png'; }}
    <img src="{{ avatarUrl }}" class="user-avatar" onerror="this.src='/uploads/avatar/default.png'">
</script>

<!-- 用户信息模板 -->
<script type="text/html" id="userinfo-tpl">
    <p><strong>{{ d.nickname || '未设置昵称' }}</strong></p>
    <p>手机号: {{ d.phone || '未绑定' }}</p>
    <p>姓名: {{ d.real_name || '未实名' }}</p>
</script>

<!-- 账户信息模板 -->
<script type="text/html" id="account-tpl">
    <p>余额: <span style="color: #f44336;">¥{{ d.balance }}</span></p>
    <p>积分: {{ d.points }}</p>
</script>

<!-- 操作模板 -->
<script type="text/html" id="operate-bar">
    <a class="layui-btn layui-btn-xs layui-btn-normal" lay-event="edit">编辑</a>
    {{# if(d.status == 1){ }}
        <a class="layui-btn layui-btn-xs layui-btn-danger" lay-event="disable">禁用</a>
    {{# } else { }}
        <a class="layui-btn layui-btn-xs layui-btn-success" lay-event="enable">启用</a>
    {{# } }}
</script>

<script src="../public/layui/layui.js"></script>
<script>
layui.use(['table', 'layer', 'form'], function(){
    var table = layui.table;
    var layer = layui.layer;
    var form = layui.form;
    var $ = layui.$;
    
    // 渲染表格
    var dataTable = table.render({
        elem: '#data-table'
        ,url: '?t=data'
        ,page: true
        ,limit: 20
        ,cols: [[
            {field:'id', width:60, title: 'ID'}
            ,{field:'avatar', title: '头像', width: 80, templet: '#avatar-tpl'}
            ,{field:'nickname', title: '用户信息', minWidth: 150, templet: '#userinfo-tpl'}
            ,{field:'balance', title: '账户信息', width: 150, templet: '#account-tpl'}
            ,{field:'is_runner', title: '跑腿员', width: 80, templet: '#runner-tpl'}
            ,{field:'status', title: '状态', width: 70, templet: '#status-tpl'}
            ,{field:'create_time', title: '注册时间', width: 150}
            ,{width:150, align:'center', toolbar: '#operate-bar', title: '操作'}
        ]]
    });
    
    // 搜索
    $('#searchBtn').on('click', function(){
        var keyword = $('#keyword-search').val();
        var status = $('#status-search').val();
        var is_runner = $('#is_runner-search').val();
        table.reload('data-table', {
            page: { curr: 1 }
            ,where: { 
                keyword: keyword,
                status: status,
                is_runner: is_runner
            }
        });
    });
    
    // 重置
    $('#resetBtn').on('click', function(){
        $('#keyword-search').val('');
        $('#status-search').val('-1');
        $('#is_runner-search').val('-1');
        form.render('select');
        table.reload('data-table', {
            page: { curr: 1 }
            ,where: { 
                keyword: '',
                status: -1,
                is_runner: -1
            }
        });
    });
    
    // 添加用户
    $('#addBtn').on('click', function(){
        layer.open({
            type: 2,
            title: '添加用户',
            content: 'user_add.php',
            area: ['500px', '480px'],
            shadeClose: false
        });
    });
    
    // 表格工具条事件
    table.on('tool(data-table)', function(obj){
        var data = obj.data;
        
        if(obj.event === 'edit'){
            layer.open({
                type: 2,
                title: '编辑用户',
                content: 'user_add.php?id=' + data.id,
                area: ['500px', '480px'],
                shadeClose: false
            });
        } else if(obj.event === 'enable'){
            toggleStatus(data.id, 1);
        } else if(obj.event === 'disable'){
            toggleStatus(data.id, 0);
        }
    });
    
    // 切换状态
    function toggleStatus(id, status) {
        var msg = status == 1 ? '确定要启用该用户吗？' : '确定要禁用该用户吗？';
        layer.confirm(msg, function(index){
            $.ajax({
                url: 'user_list.php',
                type: 'POST',
                data: {action: 'toggle_status', id: id, status: status},
                dataType: 'json',
                success: function(res){
                    if(res.code === 0){
                        layer.msg('操作成功', {icon: 1});
                        table.reload('data-table');
                    } else {
                        layer.msg(res.msg || '操作失败', {icon: 2});
                    }
                }
            });
            layer.close(index);
        });
    }
});
</script>

</body>
</html>
