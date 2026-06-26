<?php 
require("../data/class.php");

$t = isset($_GET['t']) ? $_GET['t'] : '';
$key = isset($_GET['key']) ? $_GET['key'] : '';
$page = isset($_GET['page']) ? intval($_GET['page']) : 1;

// 删除模块
if (isset($_GET['e']) && $_GET['e'] == "del") {
    $del_id = intval($_GET['del_id']);
    if($del_id > 0) {
        $sql = "DELETE FROM guests WHERE id='$del_id' LIMIT 1";
        mysqli_query($conn, $sql);
    }
    if (!empty($_SERVER['HTTP_X_REQUESTED_WITH']) && strtolower($_SERVER['HTTP_X_REQUESTED_WITH']) == 'xmlhttprequest') {
        header('Content-Type: application/json');
        echo json_encode(['code' => 0, 'msg' => '删除成功']);
        exit;
    }
    print "<script>location.href='guests_list.php?key=".$key."&page=".$page."';</script>";
    exit;
}

// 清空数据表模块
if (isset($_GET['e']) && $_GET['e'] == "clear") {
    if ($_SERVER['REQUEST_METHOD'] == 'POST') {
        $password = isset($_POST['password']) ? $_POST['password'] : '';
        
        $password_md5 = md5($password);
        $sql = "SELECT id FROM admin WHERE password='$password_md5' LIMIT 1";
        $result = mysqli_query($conn, $sql);
        
        if (mysqli_num_rows($result) > 0) {
            $sql = "TRUNCATE TABLE guests";
            if (mysqli_query($conn, $sql)) {
                header('Content-Type: application/json');
                echo json_encode(['code' => 0, 'msg' => '清空成功']);
                exit;
            } else {
                header('Content-Type: application/json');
                echo json_encode(['code' => 1, 'msg' => '清空失败']);
                exit;
            }
        } else {
            header('Content-Type: application/json');
            echo json_encode(['code' => 1, 'msg' => '密码错误']);
            exit;
        }
    }
}

// 批量重置排队模块 - 重置所有记录
if (isset($_GET['e']) && $_GET['e'] == "reset_queue") {
    if ($_SERVER['REQUEST_METHOD'] == 'POST') {
        $sql = "UPDATE guests SET status=0, assigned_count=0, order_wxid=''";
        
        if (mysqli_query($conn, $sql)) {
            $affected = mysqli_affected_rows($conn);
            header('Content-Type: application/json');
            echo json_encode(['code' => 0, 'msg' => '重置成功，共' . $affected . '条记录']);
            exit;
        } else {
            header('Content-Type: application/json');
            echo json_encode(['code' => 1, 'msg' => '重置失败：' . mysqli_error($conn)]);
            exit;
        }
    }
}

// 数据接口
if ($t == "data") {
    $page = isset($_GET['page']) ? intval($_GET['page']) : 1;
    $limit = isset($_GET['limit']) ? intval($_GET['limit']) : 20;
    
    $where = "1=1";
    if ($key != '') {
        $where .= " AND (group_name LIKE '%" . mysqli_real_escape_string($conn, $key) . "%' OR phone LIKE '%" . mysqli_real_escape_string($conn, $key) . "%' OR name1 LIKE '%" . mysqli_real_escape_string($conn, $key) . "%' OR name2 LIKE '%" . mysqli_real_escape_string($conn, $key) . "%' OR name3 LIKE '%" . mysqli_real_escape_string($conn, $key) . "%' OR name4 LIKE '%" . mysqli_real_escape_string($conn, $key) . "%' OR name5 LIKE '%" . mysqli_real_escape_string($conn, $key) . "%')";
    }

    $sql_count = "SELECT COUNT(*) as count FROM guests WHERE $where";
    $result_count = mysqli_query($conn, $sql_count);
    $row_count = mysqli_fetch_assoc($result_count);
    $count = $row_count['count'];

    $start = ($page - 1) * $limit;
    $sql = "SELECT g.* FROM guests g WHERE $where ORDER BY g.id DESC LIMIT $start, $limit";
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
    <title>客人列表</title>
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
            <a><cite>客人管理系统</cite></a>
            <a><cite>客人列表</cite></a>
        </div>
    </div>
    
    <div class="layui-row layui-col-space15">
        <div class="layui-col-md12">
            <div class="layui-card">
                <div class="layui-card-body">
                    <div class="layui-row">
                        <div class="layui-col-md12">
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: -10px;">
                                <div class="layui-btn-container" style="margin: 0;">
                                    <button class="layui-btn" id="addBtn">添加客人</button>
                                    <button class="layui-btn layui-btn-normal" id="batchAddBtn">批量添加客人</button>
                                    <button class="layui-btn layui-btn-warm" id="resetQueueBtn">批量重置排队</button>
                                    <button class="layui-btn layui-btn-danger" id="clearBtn">一键清空客人表</button>
                                </div>
                                
                                <div class="user-table-reload-btn">
                                    <div class="layui-inline">
                                        <input class="layui-input" name="key" id="key-search" placeholder="客人组名/手机号/姓名" value="<?php echo htmlspecialchars($key); ?>">
                                    </div>
                                    <button class="layui-btn" data-type="reload">搜索</button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <table class="layui-table" id="data-table" lay-filter="data-table"></table>
                </div>
            </div>
        </div>
    </div>
</div>

<script type="text/html" id="status-bar">
    {{#  if(d.status == -4){ }}
        <span class="layui-btn layui-btn-disabled layui-btn-xs layui-btn-radius">已退票</span>
    {{#  } else if(d.status == -1){ }}
        <span class="layui-btn layui-btn-primary layui-btn-xs layui-btn-radius">有错误</span>
    {{#  } else if(d.status == 0){ }}
        <span class="layui-btn layui-btn-xs layui-btn-radius">排队中</span>
    {{#  } else if(d.status == 1){ }}
        <span class="layui-btn layui-btn-danger layui-btn-xs layui-btn-radius">抢票中</span>
    {{#  } else if(d.status == 2){ }}
        <span class="layui-btn layui-btn-warm layui-btn-xs layui-btn-radius">已抢到</span>
    {{#  } else if(d.status == 3){ }}
        <span class="layui-btn layui-btn-normal layui-btn-xs layui-btn-radius">已生码</span>
    {{#  } else if(d.status == 9){ }}
        <span class="layui-btn layui-btn-normal layui-btn-xs layui-btn-radius">已付款</span>
    {{#  } }}
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
            {field:'id', width:80, title: 'ID', sort: false}
            ,{field:'group_name', title: '客人组名', width: 120, templet: function(d){
                var count = 0;
                for (var i = 1; i <= 5; i++) {
                    if (d['name' + i]) count++;
                }
                return d.group_name + ' <span class="layui-badge">' + count + '</span>';
            }}
            ,{field:'ticket_date', title: '抢票日期', width: 120, templet: function(d){
                if (!d.ticket_date) return '';
                var date = new Date(d.ticket_date);
                var month = (date.getMonth() + 1).toString().padStart(2, '0');
                var day = date.getDate().toString().padStart(2, '0');
                var priorityHtml = '';
                if (d.priority == 5) {
                    priorityHtml = '<span class="layui-badge-dot"></span>';
                } else if (d.priority == 4) {
                    priorityHtml = '<span class="layui-badge-dot layui-bg-orange"></span>';
                } else if (d.priority == 3) {
                    priorityHtml = '<span class="layui-badge-dot layui-bg-blue"></span>';
                } else if (d.priority == 2) {
                    priorityHtml = '<span class="layui-badge-dot layui-bg-green"></span>';
                }
                return month + '-' + day + ' ' + d.ticket_time + ' ' + priorityHtml;
            }}
            ,{field:'phone', title: '手机号', width: 120}
            ,{field:'status', title: '状态', width: 80, templet: '#status-bar'}
            ,{field:'remarks', title: '备注', minWidth: 150}
            ,{field:'name1', title: '姓名1', width: 80}
            ,{field:'name2', title: '姓名2', width: 80}
            ,{field:'name3', title: '姓名3', width: 80}
            ,{field:'name4', title: '姓名4', width: 80}
            ,{field:'name5', title: '姓名5', width: 80}
            ,{field:'created_at', title: '创建时间', width: 170}
            ,{width:120, align:'center', toolbar: '#operate-bar', title: '操作'}
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
            title: '添加客人',
            content: 'guest_add.php',
            area: ['800px', '668px'],
            shadeClose: false
        });
    });

    $('#batchAddBtn').on('click', function(){
        layer.open({
            type: 2,
            title: '批量添加客人',
            content: 'guest_batchadd.php',
            area: ['900px', '750px'],
            shadeClose: false
        });
    });

    $('#clearBtn').on('click', function(){
        layer.prompt({
            title: '请输入登录密码确认清空操作',
            formType: 1
        }, function(password, index){
            $.ajax({
                url: '?e=clear',
                type: 'POST',
                data: {password: password},
                dataType: 'json',
                success: function(res){
                    if(res.code === 0){
                        layer.msg('清空成功', {icon: 1});
                        table.reload('data-table');
                    } else {
                        layer.msg(res.msg, {icon: 2});
                    }
                }
            });
            layer.close(index);
        });
    });

    $('#resetQueueBtn').on('click', function(){
        layer.confirm('确定要重置所有记录到排队状态吗？<br><span style="color:red">此操作将重置整张表的所有记录！</span>', {
            btn: ['确定', '取消'],
            title: '警告'
        }, function(index){
            $.ajax({
                url: '?e=reset_queue',
                type: 'POST',
                dataType: 'json',
                success: function(res){
                    if(res.code === 0){
                        layer.msg(res.msg, {icon: 1});
                        table.reload('data-table');
                    } else {
                        layer.msg(res.msg, {icon: 2});
                    }
                },
                error: function(){
                    layer.msg('请求失败，请重试', {icon: 2});
                }
            });
            layer.close(index);
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
                title: '编辑客人',
                content: 'guest_add.php?id=' + data.id,
                area: ['800px', '668px'],
                shadeClose: false
            });
        }
    });
});
</script>
</body>
</html>
