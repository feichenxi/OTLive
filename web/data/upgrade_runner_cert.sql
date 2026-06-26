-- 数据库升级脚本
-- 为 runner_cert 表添加紧急联系人字段

-- 添加紧急联系人姓名字段
ALTER TABLE `runner_cert` 
ADD COLUMN `emergency_contact` varchar(50) DEFAULT '' COMMENT '紧急联系人姓名' 
AFTER `vehicle_type`;

-- 添加紧急联系人电话字段
ALTER TABLE `runner_cert` 
ADD COLUMN `emergency_phone` varchar(20) DEFAULT '' COMMENT '紧急联系人电话' 
AFTER `emergency_contact`;
