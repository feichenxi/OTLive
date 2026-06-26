<?php
require("../data/class.php");

$id = isset($_GET['id']) ? intval($_GET['id']) : 0;
$banner = null;
$is_edit = false;

if ($id > 0) {
    $banner = Table_Info("banners", "alldata", "id='$id'");
    if ($banner) {
        $is_edit = true;
    }
}

// 定义位置选项
$positionOptions = [
    'index' => '首页轮播图',
    'category' => '分类页广告',
    'order' => '下单页广告',
    'mine' => '我的页广告',
    'popup' => '弹窗广告',
    'login' => '登录轮播图'
];

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $title = mysqli_real_escape_string($conn, $_POST['title']);
    $link_url = mysqli_real_escape_string($conn, $_POST['link_url']);
    $sort = intval($_POST['sort']);
    $status = intval($_POST['status']);
    $position = mysqli_real_escape_string($conn, $_POST['position']);
    
    // 处理图片上传
    $image = '';
    if (isset($_FILES['image_file']) && $_FILES['image_file']['error'] == 0) {
        $uploadDir = '../uploads/banner/';
        if (!is_dir($uploadDir)) {
            mkdir($uploadDir, 0755, true);
        }
        
        $allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
        if (!in_array($_FILES['image_file']['type'], $allowedTypes)) {
            echo "<script>alert('只允许上传 JPG、PNG、GIF、WEBP 格式的图片');</script>";
            goto show_form;
        }
        
        $maxSize = 5 * 1024 * 1024;
        if ($_FILES['image_file']['size'] > $maxSize) {
            echo "<script>alert('图片大小不能超过 5MB');</script>";
            goto show_form;
        }
        
        $extension = pathinfo($_FILES['image_file']['name'], PATHINFO_EXTENSION);
        $filename = 'banner_' . date('YmdHis') . '_' . rand(1000, 9999) . '.' . $extension;
        $filepath = $uploadDir . $filename;
        
        if (move_uploaded_file($_FILES['image_file']['tmp_name'], $filepath)) {
            $image = 'uploads/banner/' . $filename;
        } else {
            echo "<script>alert('文件上传失败');</script>";
            goto show_form;
        }
    }
    
    // 如果是编辑且没有新上传图片，保留原图
    if ($id > 0 && empty($image) && isset($_POST['old_image'])) {
        $image = mysqli_real_escape_string($conn, $_POST['old_image']);
    }
    
    if (empty($image)) {
        echo "<script>alert('请上传图片');</script>";
        goto show_form;
    }
    
    $image = mysqli_real_escape_string($conn, $image);
    
    if ($id > 0) {
        $sql = "UPDATE banners SET image='$image', title='$title', link_url='$link_url', position='$position', sort='$sort', status='$status', update_time=NOW() WHERE id='$id'";
    } else {
        $sql = "INSERT INTO banners (image, title, link_url, position, sort, status, create_time, update_time) VALUES ('$image', '$title', '$link_url', '$position', '$sort', '$status', NOW(), NOW())";
    }
    
    if (mysqli_query($conn, $sql)) {
        echo "<script>parent.layer.closeAll();parent.layui.table.reload('data-table');</script>";
    } else {
        echo "<script>alert('保存失败：" . mysqli_error($conn) . "');</script>";
    }
    exit;
}

show_form:
?>
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title><?php echo $is_edit ? '编辑轮播图' : '添加轮播图'; ?></title>
    <meta name="renderer" content="webkit">
    <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <link rel="stylesheet" href="../public/layui/css/layui.css" media="all">
    <link rel="stylesheet" href="../public/style/admin.css" media="all">
    <style>
        .upload-area { 
            border: 2px dashed #ddd; 
            padding: 30px; 
            text-align: center; 
            cursor: pointer; 
            border-radius: 4px;
            transition: all 0.3s;
            background: #fafafa;
        }
        .upload-area:hover { border-color: #1E9FFF; background: #f0f9ff; }
        .upload-area i { font-size: 48px; color: #999; }
        .upload-area p { margin-top: 10px; color: #666; }
        .upload-input { display: none; }
        .upload-preview { margin-top: 10px; position: relative; display: inline-block; }
        .upload-preview img { max-width: 100%; max-height: 200px; border-radius: 4px; border: 1px solid #ddd; }
        .upload-preview .delete-btn { 
            position: absolute; 
            top: -10px; 
            right: -10px; 
            width: 28px; 
            height: 28px; 
            background: #ff5722; 
            color: #fff; 
            border-radius: 50%; 
            text-align: center; 
            line-height: 28px; 
            cursor: pointer; 
            font-size: 16px;
        }
    </style>
</head>
<body>
<div class="layui-fluid">
    <div class="layui-card">
        <div class="layui-card-body">
            <form class="layui-form" lay-filter="bannerForm" action="" method="post" enctype="multipart/form-data">
                <input type="hidden" name="id" value="<?php echo $id; ?>">
                <?php if ($banner && !empty($banner['image'])): ?>
                <input type="hidden" name="old_image" value="<?php echo $banner['image']; ?>">
                <?php endif; ?>
                
                <!-- 图片上传 -->
                <div class="layui-form-item">
                    <label class="layui-form-label">图片</label>
                    <div class="layui-input-block">
                        <div class="upload-area" id="uploadArea" onclick="document.getElementById('image_file').click()">
                            <i class="layui-icon layui-icon-upload"></i>
                            <p>点击上传图片，或拖拽图片到此处</p>
                            <p style="font-size: 12px; color: #999;">支持 JPG、PNG、GIF、WEBP，最大 5MB</p>
                        </div>
                        <input type="file" name="image_file" id="image_file" class="upload-input" accept="image/*">
                        
                        <div class="upload-preview" id="uploadPreview" style="display: <?php echo ($banner && !empty($banner['image'])) ? 'inline-block' : 'none'; ?>;">
                            <img src="<?php echo ($banner && !empty($banner['image'])) ? '../' . $banner['image'] : ''; ?>" id="preview_image">
                            <span class="delete-btn" onclick="clearImage(event)">×</span>
                        </div>
                    </div>
                </div>
                
                <!-- 位置选择 -->
                <div class="layui-form-item">
                    <label class="layui-form-label">位置</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <select name="position" lay-verify="required">
                            <?php foreach ($positionOptions as $key => $name): ?>
                            <option value="<?php echo $key; ?>" <?php echo ($banner && $banner['position'] == $key) ? 'selected' : ''; ?>><?php echo $name; ?></option>
                            <?php endforeach; ?>
                        </select>
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">标题</label>
                    <div class="layui-input-inline" style="width: 300px;">
                        <input type="text" name="title" placeholder="请输入标题（可选）" autocomplete="off" class="layui-input" value="<?php echo $banner ? htmlspecialchars($banner['title']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">链接</label>
                    <div class="layui-input-inline" style="width: 300px;">
                        <input type="text" name="link_url" placeholder="请输入跳转链接（可选）" autocomplete="off" class="layui-input" value="<?php echo $banner ? htmlspecialchars($banner['link_url']) : ''; ?>">
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">排序</label>
                    <div class="layui-input-inline" style="width: 100px;">
                        <input type="number" name="sort" placeholder="数值越大越靠前" autocomplete="off" class="layui-input" value="<?php echo $banner ? $banner['sort'] : '0'; ?>">
                    </div>
                    <div class="layui-form-mid layui-word-aux">数值越大排序越靠前</div>
                </div>
                
                <div class="layui-form-item">
                    <label class="layui-form-label">状态</label>
                    <div class="layui-input-inline" style="width: 200px;">
                        <select name="status" lay-verify="required">
                            <option value="1" <?php echo (!$banner || $banner['status'] == 1) ? 'selected' : ''; ?>>显示</option>
                            <option value="0" <?php echo ($banner && $banner['status'] == 0) ? 'selected' : ''; ?>>隐藏</option>
                        </select>
                    </div>
                </div>
                
                <div class="layui-form-item">
                    <div class="layui-input-block">
                        <button class="layui-btn" lay-submit lay-filter="saveBtn">立即提交</button>
                        <button type="button" class="layui-btn layui-btn-primary" onclick="closeLayer()">取消</button>
                    </div>
                </div>
            </form>
        </div>
    </div>
</div>

<script src="../public/layui/layui.js"></script>
<script>
layui.config({
    base: '../public/'
}).use(['form', 'layer'], function(){
    var form = layui.form
    ,layer = layui.layer
    ,$ = layui.$;
    
    var hasImage = <?php echo ($banner && !empty($banner['image'])) ? 'true' : 'false'; ?>;
    
    // 文件选择事件
    document.getElementById('image_file').addEventListener('change', function(e) {
        var file = e.target.files[0];
        if (file) {
            var reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById('preview_image').src = e.target.result;
                document.getElementById('uploadPreview').style.display = 'inline-block';
                document.getElementById('uploadArea').style.display = 'none';
                hasImage = true;
            };
            reader.readAsDataURL(file);
        }
    });
    
    // 拖拽上传
    var uploadArea = document.getElementById('uploadArea');
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.style.borderColor = '#1E9FFF';
        this.style.background = '#f0f9ff';
    });
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.style.borderColor = '#ddd';
        this.style.background = '#fafafa';
    });
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        this.style.borderColor = '#ddd';
        this.style.background = '#fafafa';
        var files = e.dataTransfer.files;
        if (files.length > 0) {
            var file = files[0];
            if (file.type.startsWith('image/')) {
                document.getElementById('image_file').files = files;
                var reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('preview_image').src = e.target.result;
                    document.getElementById('uploadPreview').style.display = 'inline-block';
                    document.getElementById('uploadArea').style.display = 'none';
                    hasImage = true;
                };
                reader.readAsDataURL(file);
            } else {
                layer.msg('请选择图片文件', {icon: 2});
            }
        }
    });
    
    // 清除图片
    window.clearImage = function(e) {
        if (e) e.stopPropagation();
        document.getElementById('image_file').value = '';
        document.getElementById('uploadPreview').style.display = 'none';
        document.getElementById('uploadArea').style.display = 'block';
        hasImage = false;
    };
    
    // 关闭弹窗
    window.closeLayer = function() {
        parent.layer.close(parent.layer.getFrameIndex(window.name));
    };
    
    // 渲染表单
    form.render();
    
    // 表单提交验证 - 使用原生表单提交，避免LayUI拦截
    document.querySelector('form').addEventListener('submit', function(e) {
        if (!hasImage) {
            e.preventDefault();
            layer.msg('请上传图片', {icon: 2});
            return false;
        }
        // 允许表单提交
        return true;
    });
    
    // LayUI form提交事件（备用）
    form.on('submit(saveBtn)', function(data){
        if (!hasImage) {
            layer.msg('请上传图片', {icon: 2});
            return false;
        }
        // 返回true让表单正常提交
        return true;
    });
});
</script>
</body>
</html>
