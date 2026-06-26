<?php 
require("../data/class.php");

$t = isset($_GET['t']) ? $_GET['t'] : '';
$key = isset($_GET['key']) ? $_GET['key'] : '';
$page = isset($_GET['page']) ? intval($_GET['page']) : 1;

// 删除模块
if (isset($_GET['e']) && $_GET['e'] == "del") {
    $del_id = intval($_GET['del_id']);
    if($del_id > 0) {
        $sql = "DELETE FROM machines WHERE id='$del_id' LIMIT 1";
        mysqli_query($conn, $sql);
    }
    if (!empty($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) == 'xmlhttprequest') {
        header('Content-Type: application/json');
        echo json_encode(['code' => 0, 'msg' => '删除成功']);
        exit;
    }
    print "<script>location.href='machines_list.php?key=".$key."&page=".$page."';</script>";
    exit;
}

// 数据接口
if ($t == "data") {
    $page = isset($_GET['page']) ? intval($_GET['page']) : 1;
    $limit = isset($_GET['limit']) ? intval($_GET['limit']) : 20;
    
    $where = "1=1";
    if ($key != '') {
        $where .= " AND (machine LIKE '%" . mysqli_real_escape_string($conn, $key) . "%' OR ip LIKE '%" . mysqli_real_escape_string($conn, $key) . "%')";
    }

    $sql_count = "SELECT COUNT(*) as count FROM machines WHERE $where";
    $result_count = mysqli_query($conn, $sql_count);
    $row_count = mysqli_fetch_assoc($result_count);
    $count = $row_count['count'];

    $start = ($page - 1) * $limit;
    $sql = "SELECT m.* FROM machines m WHERE $where ORDER BY m.id DESC LIMIT $start, $limit";
    $result = mysqli_query($conn, $sql);

    $data = array();
    while($row = mysqli_fetch_assoc($result)) {
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
    <title>运行机</title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
</head>
<body>

<div class="layui-fluid">
    <div class="layui-card layadmin-header">
        <div class="layui-breadcrumb" lay-filter="breadcrumb">
            <a lay-href="">主页</a>
            <a><cite>运行机</cite></a>
        </div>
    </div>
    
    <div class="layui-row layui-col-space15">
        <div class="layui-col-md12">
            <div class="layui-card">
                <div class="layui-card-body">
                    <div class="layui-btn-group">
                        <button class="layui-btn" id="addBtn">添加运行机</button>
                    </div>
                    
                    <div class="user-table-reload-btn" style="float: right; margin-left: 10px;">
                        <div class="layui-inline">
                            <input class="layui-input" name="key" id="key-search" placeholder="机器名称/地区" value="<?php echo htmlspecialchars($key); ?>">
                        </div>
                        <button class="layui-btn" data-type="reload">搜索</button>
                    </div>
                    <div style="clear: both;"></div>
                    
                    <table class="layui-table" id="data-table" lay-filter="data-table"></table>
                </div>
            </div>
        </div>
    </div>
</div>

<script type="text/html" id="proxy-bar">
    {{ d.proxy || '-' }}
</script>

<script type="text/html" id="operate-bar">
    <a class="layui-btn layui-btn-xs layui-btn-normal" lay-event="edit">编辑</a>
    <a class="layui-btn layui-btn-danger layui-btn-xs" lay-event="del">删除</a>
</script>

<script src="../public/layui/layui.js"></script>
<script>
layui.config({
    base: '../public/'
}).use(['table', 'layer', 'form'], function(){
    var table = layui.table
    ,layer = layui.layer
    ,$ = layui.$;
  
    var dataTable = table.render({
        elem: '#data-table'
        ,url: '?t=data'
        ,page: true
        ,limit: 20
        ,cols: [[
            {field:'id', width:80, title: 'ID'}
            ,{field:'machine', title: '机器名称', width: 150}
            ,{field:'ip', title: '地区', width: 150}
            ,{field:'proxy', title: '代理IP', width: 100, templet: '#proxy-bar'}
            ,{field:'time_login', title: '登录时间', width: 170, sort: false}
            ,{field:'time_buy', title: '查票时间', width: 170, sort: false}
            ,{field:'num_login', title: '登录账号', width: 100, sort: false}
            ,{field:'remarks', title: '备注', minWidth: 200}
            ,{field:'created_at', title: '创建时间', width: 170, sort: false}
            ,{fixed: 'right', width:120, align:'center', toolbar: '#operate-bar', title: '操作'}
        ]]
    });
    
    var active = {
        reload: function(){
            var keySearch = $('#key-search');
            table.reload('data-table', {
                page: { curr: 1 }
                ,where: { key: keySearch.val() }
            });
        }
    };
    
    $('.user-table-reload-btn .layui-btn').on('click', function(){
        var type = $(this).data('type');
        active[type] ? active[type].call(this) : '';
    });
    
    $('#addBtn').on('click', function(){
        layer.open({
            type: 2,
            title: '添加运行机',
            content: 'machines_add.php',
            area: ['660px', '360px'],
            shadeClose: false
        });
    });

    table.on('tool(data-table)', function(obj){
        var data = obj.data;
        if(obj.event === 'del'){
            layer.confirm('确定要删除吗？', function(index){
                $.ajax({
                    url: '?e=del&del_id=' + data.id,
                    type: 'GET',
                    dataType: 'json',
                    success: function(res){
                        if(res.code === 0){
                            layer.msg('删除成功');
                            table.reload('data-table');
                        } else {
                            layer.msg('删除失败');
                        }
                    }
                });
                layer.close(index);
            });
        } else if(obj.event === 'edit'){
            layer.open({
                type: 2,
                title: '编辑运行机',
                content: 'machines_add.php?id=' + data.id,
                area: ['660px', '360px'],
                shadeClose: false
            });
        }
    });
});
</script>
</body>
</html>
