<?php
/**
 * 数据库升级脚本 - 添加紧急联系人字段
 */
require_once("data/class.php");

$conn = $_ENV['conn'];

echo "开始升级数据库...\n";

// 添加紧急联系人字段
$sql1 = "ALTER TABLE `runner_cert` 
         ADD COLUMN `emergency_contact` varchar(50) DEFAULT '' COMMENT '紧急联系人姓名' 
         AFTER `vehicle_type`";
echo "执行 SQL: $sql1\n";

if (mysqli_query($conn, $sql1)) {
    echo "✓ 添加 emergency_contact 字段成功\n";
} else {
    echo "⚠ emergency_contact 字段可能已存在: " . mysqli_error($conn) . "\n";
}

// 添加紧急联系人电话字段
$sql2 = "ALTER TABLE `runner_cert` 
         ADD COLUMN `emergency_phone` varchar(20) DEFAULT '' COMMENT '紧急联系人电话' 
         AFTER `emergency_contact`";
echo "执行 SQL: $sql2\n";

if (mysqli_query($conn, $sql2)) {
    echo "✓ 添加 emergency_phone 字段成功\n";
} else {
    echo "⚠ emergency_phone 字段可能已存在: " . mysqli_error($conn) . "\n";
}

echo "\n数据库升级完成！\n";
