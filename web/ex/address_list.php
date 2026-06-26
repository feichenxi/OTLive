<?php
require("../data/class.php");

// 处理AJAX请求
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $action = $_POST['action'];
    
    switch ($action) {
        case 'delete':
            $id = intval($_POST['id'] ?? 0);
            
            if ($id <= 0) {
                header('Content-Type: application/json');
                echo json_encode(['code' => 1, 'msg' => '参数错误']);
                exit;
            }
            
            $sql = "UPDATE user_address SET delete_time = NOW() WHERE id='$id'";
            if (mysqli_query($conn, $sql)) {
                header('Content-Type: application/json');
                echo json_encode(['code' => 0, 'msg' => '删除成功']);
            } else {
                header('Content-Type: application/json');
                echo json_encode(['code' => 1, 'msg' => '删除失败: ' . mysqli_error($conn)]);
            }
            exit;
            
        case 'set_default':
            $id = intval($_POST['id'] ?? 0);
            
            if ($id <= 0) {
                header('Content-Type: application/json');
                echo json_encode(['code' => 1, 'msg' => '参数错误']);
                exit;
            }
            
            // 获取地址信息
            $sql = "SELECT user_id FROM user_address WHERE id='$id' AND delete_time IS NULL";
            $result = mysqli_query($conn, $sql);
            $address = mysqli_fetch_assoc($result);
            
            if (!$address) {
                header('Content-Type: application/json');
                echo json_encode(['code' => 1, 'msg' => '地址不存在']);
                exit;
            }
            
            $user_id = $address['user_id'];
            
            // 先取消该用户所有默认地址
            mysqli_query($conn, "UPDATE user_address SET is_default = 0 WHERE user_id = '$user_id'");
            
            // 设置新的默认地址
            $sql = "UPDATE user_address SET is_default = 1 WHERE id='$id'";
            if (mysqli_query($conn, $sql)) {
                header('Content-Type: application/json');
                echo json_encode(['code' => 0, 'msg' => '设置成功']);
            } else {
                header('Content-Type: application/json');
                echo json_encode(['code' => 1, 'msg' => '设置失败: ' . mysqli_error($conn)]);
            }
            exit;
    }
}

// 数据接口
if (isset($_GET['t']) && $_GET['t'] == 'data') {
    $page = isset($_GET['page']) ? intval($_GET['page']) : 1;
    $limit = isset($_GET['limit']) ? intval($_GET['limit']) : 20;
    $offset = ($page - 1) * $limit;
    
    $where = "WHERE a.delete_time IS NULL";
    $keyword = isset($_GET['keyword']) ? trim($_GET['keyword']) : '';
    $user_id = isset($_GET['user_id']) ? intval($_GET['user_id']) : 0;
    
    if ($keyword) {
        $keyword_escaped = mysqli_real_escape_string($conn, $keyword);
        $where .= " AND (a.name LIKE '%{$keyword_escaped}%' OR a.phone LIKE '%{$keyword_escaped}%' OR a.address LIKE '%{$keyword_escaped}%' OR u.nickname LIKE '%{$keyword_escaped}%' OR u.phone LIKE '%{$keyword_escaped}%')";
    }
    
    if ($user_id > 0) {
        $where .= " AND a.user_id = {$user_id}";
    }
    
    $sql_count = "SELECT COUNT(*) as count FROM user_address a LEFT JOIN users u ON a.user_id = u.id {$where}";
    $result_count = mysqli_query($conn, $sql_count);
    $count = mysqli_fetch_assoc($result_count)['count'];
    
    $sql = "SELECT a.*, u.nickname as user_nickname, u.phone as user_phone 
            FROM user_address a 
            LEFT JOIN users u ON a.user_id = u.id 
            {$where} 
            ORDER BY a.create_time DESC 
            LIMIT {$offset}, {$limit}";
    $result = mysqli_query($conn, $sql);
    
    $data = array();
    while ($row = mysqli_fetch_assoc($result)) {
        $row['is_default_text'] = $row['is_default'] ? '是' : '否';
        $row['create_time_text'] = $row['create_time'] ?? '-';
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
    <title>地址管理</title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-header">地址管理</div>
        <div class="layui-card-body">
            <!-- 搜索表单 -->
            <div class="layui-form layui-form-pane">
                <div class="layui-form-item">
                    <div class="layui-inline">
                        <label class="layui-form-label">关键词</label>
                        <div class="layui-input-inline">
                            <input type="text" name="keyword" id="keyword" placeholder="联系人/电话/地址/用户" autocomplete="off" class="layui-input">
                        </div>
                    </div>
                    <div class="layui-inline">
                        <label class="layui-form-label">用户ID</label>
                        <div class="layui-input-inline" style="width: 100px;">
                            <input type="number" name="user_id" id="user_id" placeholder="用户ID" autocomplete="off" class="layui-input">
                        </div>
                    </div>
                    <div class="layui-inline">
                        <button class="layui-btn" lay-submit lay-filter="formSearch"><i class="layui-icon">&#xe615;</i> 搜索</button>
                        <button type="reset" class="layui-btn layui-btn-primary"><i class="layui-icon">&#xe669;</i> 重置</button>
                    </div>
                </div>
            </div>
            
            <!-- 数据表格 -->
            <table class="layui-hide" id="addressTable" lay-filter="addressTable"></table>
        </div>
    </div>
</div>

<script type="text/html" id="tableToolbar">
    <div class="layui-btn-container">
        <span class="layui-badge layui-bg-gray">提示：地址由用户在App端管理，此处仅作查看</span>
    </div>
</script>

<script type="text/html" id="tableOperate">
    <a class="layui-btn layui-btn-xs {{# if(d.is_default == 1){ }}layui-btn-disabled{{# } else { }}layui-btn-normal{{# } }}" lay-event="setDefault">设为默认</a>
    <a class="layui-btn layui-btn-danger layui-btn-xs" lay-event="del">删除</a>
</script>

<script type="text/html" id="addressTpl">
    <div>
        <div style="font-weight: bold;">{{d.address}}</div>
        {{# if(d.detail){ }}
        <div style="color: #666; font-size: 12px;">{{d.detail}}</div>
        {{# } }}
    </div>
</script>

<script type="text/html" id="defaultTpl">
    {{# if(d.is_default == 1){ }}
    <span class="layui-badge layui-bg-green">默认</span>
    {{# } else { }}
    <span class="layui-badge layui-bg-gray">普通</span>
    {{# } }}
</script>

<script type="text/html" id="userTpl">
    {{# if(d.user_nickname){ }}
    <div>
        <div>{{d.user_nickname}}</div>
        <div style="color: #666; font-size: 12px;">ID: {{d.user_id}}</div>
    </div>
    {{# } else { }}
    <span style="color: #999;">用户已删除</span>
    {{# } }}
</script>

<script src="../public/layui/layui.js"></script>
<script>
layui.use(['table', 'form', 'layer'], function(){
    var table = layui.table;
    var form = layui.form;
    var layer = layui.layer;
    
    // 渲染表格
    var tableIns = table.render({
        elem: '#addressTable',
        url: '?t=data',
        page: true,
        limit: 20,
        limits: [10, 20, 50, 100],
        toolbar: '#tableToolbar',
        defaultToolbar: ['filter', 'exports', 'print'],
        cols: [[
            {field: 'id', title: 'ID', width: 70, sort: true},
            {field: 'user_id', title: '用户信息', width: 120, templet: '#userTpl'},
            {field: 'name', title: '联系人', width: 100},
            {field: 'phone', title: '联系电话', width: 120},
            {field: 'address', title: '地址', minWidth: 200, templet: '#addressTpl'},
            {field: 'is_default', title: '默认', width: 80, align: 'center', templet: '#defaultTpl'},
            {field: 'order_count', title: '订单数', width: 80, align: 'center'},
            {field: 'create_time', title: '创建时间', width: 160},
            {title: '操作', width: 150, align: 'center', toolbar: '#tableOperate'}
        ]],
        response: {
            statusCode: 0
        },
        parseData: function(res) {
            return {
                "code": res.code,
                "msg": res.msg,
                "count": res.count,
                "data": res.data
            };
        }
    });
    
    // 搜索
    form.on('submit(formSearch)', function(data){
        tableIns.reload({
            where: {
                keyword: $('#keyword').val(),
                user_id: $('#user_id').val()
            },
            page: {curr: 1}
        });
        return false;
    });
    
    // 监听工具条
    table.on('tool(addressTable)', function(obj){
        var data = obj.data;
        
        if(obj.event === 'del'){
            layer.confirm('确定删除该地址吗？', function(index){
                $.ajax({
                    url: '',
                    type: 'POST',
                    data: {
                        action: 'delete',
                        id: data.id
                    },
                    dataType: 'json',
                    success: function(res){
                        if(res.code === 0){
                            layer.msg('删除成功', {icon: 1});
                            obj.del();
                        } else {
                            layer.msg(res.msg, {icon: 2});
                        }
                    }
                });
                layer.close(index);
            });
        } else if(obj.event === 'setDefault'){
            if(data.is_default == 1){
                layer.msg('该地址已是默认地址', {icon: 0});
                return;
            }
            $.ajax({
                url: '',
                type: 'POST',
                data: {
                    action: 'set_default',
                    id: data.id
                },
                dataType: 'json',
                success: function(res){
                    if(res.code === 0){
                        layer.msg('设置成功', {icon: 1});
                        tableIns.reload();
                    } else {
                        layer.msg(res.msg, {icon: 2});
                    }
                }
            });
        }
    });
});
</script>
</body>
</html>
