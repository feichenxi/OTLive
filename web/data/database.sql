-- ========================================================
-- EXHome 社区跑腿服务平台 - 数据库结构
-- 数据库: exhome
-- 字符集: utf8mb4
-- 版本: 1.0.0
-- ========================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ========================================================
-- 1. 管理员表
-- ========================================================
DROP TABLE IF EXISTS `admin`;
CREATE TABLE `admin` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '管理员ID',
  `username` varchar(50) NOT NULL DEFAULT '' COMMENT '登录账号',
  `password` varchar(255) NOT NULL DEFAULT '' COMMENT '登录密码(MD5)',
  `name` varchar(50) NOT NULL DEFAULT '' COMMENT '显示名称',
  `power` tinyint(1) NOT NULL DEFAULT '0' COMMENT '权限等级(0=普通,1=超级管理员)',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '状态(0=禁用,1=启用)',
  `last_login_time` datetime DEFAULT NULL COMMENT '最后登录时间',
  `last_login_ip` varchar(50) DEFAULT '' COMMENT '最后登录IP',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员表';

-- 插入默认管理员账号 (密码: admin123)
INSERT INTO `admin` (`id`, `username`, `password`, `name`, `power`, `status`, `create_time`) VALUES
(1, 'admin', '0192023a7bbd73250516f069df18b500', '超级管理员', 1, 1, NOW());

-- ========================================================
-- 2. 用户表
-- ========================================================
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `openid` varchar(100) NOT NULL DEFAULT '' COMMENT '微信OpenID',
  `unionid` varchar(100) DEFAULT '' COMMENT '微信UnionID',
  `nickname` varchar(100) DEFAULT '' COMMENT '昵称',
  `avatar` varchar(255) DEFAULT '' COMMENT '头像URL',
  `phone` varchar(20) DEFAULT '' COMMENT '手机号',
  `real_name` varchar(50) DEFAULT '' COMMENT '真实姓名',
  `gender` tinyint(1) DEFAULT '0' COMMENT '性别(0=未知,1=男,2=女)',
  `birthday` date DEFAULT NULL COMMENT '生日',
  `balance` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '账户余额',
  `points` int(11) NOT NULL DEFAULT '0' COMMENT '积分',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '状态(0=禁用,1=正常)',
  `is_runner` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否跑腿员(0=否,1=是)',
  `runner_status` tinyint(1) NOT NULL DEFAULT '0' COMMENT '跑腿员状态(0=未认证,1=审核中,2=已通过,3=已拒绝)',
  `id_card` varchar(20) DEFAULT '' COMMENT '身份证号',
  `id_card_front` varchar(255) DEFAULT '' COMMENT '身份证正面照',
  `id_card_back` varchar(255) DEFAULT '' COMMENT '身份证反面照',
  `emergency_contact` varchar(50) DEFAULT '' COMMENT '紧急联系人',
  `emergency_phone` varchar(20) DEFAULT '' COMMENT '紧急联系人电话',
  `login_ip` varchar(50) DEFAULT '' COMMENT '最后登录IP',
  `login_time` datetime DEFAULT NULL COMMENT '最后登录时间',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `openid` (`openid`),
  KEY `phone` (`phone`),
  KEY `status` (`status`),
  KEY `is_runner` (`is_runner`),
  KEY `runner_status` (`runner_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- ========================================================
-- 3. 用户地址表
-- ========================================================
DROP TABLE IF EXISTS `user_address`;
CREATE TABLE `user_address` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '地址ID',
  `user_id` int(11) unsigned NOT NULL DEFAULT '0' COMMENT '用户ID',
  `name` varchar(50) NOT NULL DEFAULT '' COMMENT '联系人姓名',
  `phone` varchar(20) NOT NULL DEFAULT '' COMMENT '联系人电话',
  `province` varchar(50) NOT NULL DEFAULT '' COMMENT '省份',
  `city` varchar(50) NOT NULL DEFAULT '' COMMENT '城市',
  `district` varchar(50) NOT NULL DEFAULT '' COMMENT '区县',
  `address` varchar(255) NOT NULL DEFAULT '' COMMENT '详细地址',
  `full_address` varchar(500) NOT NULL DEFAULT '' COMMENT '完整地址',
  `longitude` decimal(10,7) DEFAULT NULL COMMENT '经度',
  `latitude` decimal(10,7) DEFAULT NULL COMMENT '纬度',
  `is_default` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否默认(0=否,1=是)',
  `tag` varchar(20) DEFAULT '' COMMENT '标签(家/公司/学校)',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '状态(0=删除,1=正常)',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `is_default` (`is_default`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户地址表';

-- ========================================================
-- 4. 快递代取订单表
-- ========================================================
DROP TABLE IF EXISTS `orders_pickup`;
CREATE TABLE `orders_pickup` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '订单ID',
  `order_no` varchar(50) NOT NULL DEFAULT '' COMMENT '订单编号',
  `user_id` int(11) unsigned NOT NULL DEFAULT '0' COMMENT '下单用户ID',
  `runner_id` int(11) unsigned DEFAULT '0' COMMENT '接单跑腿员ID',
  `status` tinyint(1) NOT NULL DEFAULT '0' COMMENT '订单状态(0=待支付,1=待接单,2=已接单,3=配送中,4=已完成,5=已取消)',
  `pickup_codes` text COMMENT '取件码信息(JSON数组)',
  `pickup_images` text COMMENT '取件码图片(JSON数组，用于AI识别后查看)',
  `package_count` int(11) NOT NULL DEFAULT '1' COMMENT '快递数量',
  `weight` decimal(6,2) DEFAULT '0.00' COMMENT '预估重量(kg)',
  `delivery_address_id` int(11) unsigned DEFAULT '0' COMMENT '收货地址ID',
  `delivery_address` varchar(500) DEFAULT '' COMMENT '收货地址文本',
  `delivery_latitude` decimal(10,7) DEFAULT NULL COMMENT '收货纬度',
  `delivery_longitude` decimal(10,7) DEFAULT NULL COMMENT '收货经度',
  `delivery_name` varchar(50) DEFAULT '' COMMENT '收货联系人',
  `delivery_phone` varchar(20) DEFAULT '' COMMENT '收货联系电话',
  `appointment_starttime` datetime DEFAULT NULL COMMENT '预约开始时间',
  `appointment_endtime` datetime DEFAULT NULL COMMENT '预约结束时间',
  `base_fee` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '基础配送费',
  `extra_package_fee` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '超件费(超过基础件数的费用)',
  `extra_weight_fee` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '超重费(超过基础重量的费用)',
  `total_amount` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '订单总金额',
  `pay_amount` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '实际支付金额',
  `pay_type` tinyint(1) DEFAULT '0' COMMENT '支付方式(0=未支付,1=微信支付,2=支付宝支付,9=余额支付)',
  `transaction_id` varchar(100) DEFAULT '' COMMENT '第三方支付流水号',
  `pay_time` datetime DEFAULT NULL COMMENT '支付时间',
  `pay_trade_no` varchar(100) DEFAULT '' COMMENT '支付流水号',
  `accept_time` datetime DEFAULT NULL COMMENT '接单时间',
  `pickup_time` datetime DEFAULT NULL COMMENT '取货时间',
  `complete_time` datetime DEFAULT NULL COMMENT '完成时间',
  `cancel_time` datetime DEFAULT NULL COMMENT '取消时间',
  `cancel_reason` varchar(255) DEFAULT '' COMMENT '取消原因',
  `cancel_by` tinyint(1) DEFAULT '0' COMMENT '取消方(0=未取消,1=用户,2=跑腿员,3=系统)',
  `remark` varchar(500) DEFAULT '' COMMENT '备注',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `order_no` (`order_no`),
  KEY `user_id` (`user_id`),
  KEY `runner_id` (`runner_id`),
  KEY `status` (`status`),
  KEY `pay_type` (`pay_type`),
  KEY `create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='快递代取订单表';

-- ========================================================
-- 5. 订单状态流水表
-- ========================================================
DROP TABLE IF EXISTS `order_logs`;
CREATE TABLE `order_logs` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '日志ID',
  `order_id` int(11) unsigned NOT NULL DEFAULT '0' COMMENT '订单ID',
  `order_no` varchar(50) NOT NULL DEFAULT '' COMMENT '订单编号',
  `status` tinyint(1) NOT NULL DEFAULT '0' COMMENT '订单状态',
  `status_text` varchar(50) NOT NULL DEFAULT '' COMMENT '状态描述',
  `operator_id` int(11) unsigned DEFAULT '0' COMMENT '操作人ID',
  `operator_type` tinyint(1) DEFAULT '1' COMMENT '操作人类型(1=用户,2=跑腿员,3=系统)',
  `operator_name` varchar(50) DEFAULT '' COMMENT '操作人名称',
  `content` text COMMENT '操作内容',
  `ip` varchar(50) DEFAULT '' COMMENT '操作IP',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `order_id` (`order_id`),
  KEY `order_no` (`order_no`),
  KEY `status` (`status`),
  KEY `create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单状态流水表';

-- ========================================================
-- 6. 跑腿员认证表
-- ========================================================
DROP TABLE IF EXISTS `runner_cert`;
CREATE TABLE `runner_cert` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '认证ID',
  `user_id` int(11) unsigned NOT NULL DEFAULT '0' COMMENT '用户ID',
  `real_name` varchar(50) NOT NULL DEFAULT '' COMMENT '真实姓名',
  `id_card` varchar(20) NOT NULL DEFAULT '' COMMENT '身份证号',
  `id_card_front` varchar(255) DEFAULT '' COMMENT '身份证正面照',
  `id_card_back` varchar(255) DEFAULT '' COMMENT '身份证反面照',
  `id_card_hand` varchar(255) DEFAULT '' COMMENT '手持身份证照片',
  `health_cert` varchar(255) DEFAULT '' COMMENT '健康证照片',
  `work_city` varchar(50) DEFAULT '' COMMENT '工作城市',
  `work_district` varchar(100) DEFAULT '' COMMENT '工作区域',
  `vehicle_type` varchar(20) DEFAULT '' COMMENT '交通工具(electric=电动车,motorcycle=摩托车,car=汽车,bicycle=自行车)',
  `emergency_contact` varchar(50) DEFAULT '' COMMENT '紧急联系人姓名',
  `emergency_phone` varchar(20) DEFAULT '' COMMENT '紧急联系人电话',
  `status` tinyint(1) NOT NULL DEFAULT '0' COMMENT '认证状态(0=待审核,1=已通过,2=已拒绝,3=已禁用)',
  `reject_reason` varchar(255) DEFAULT '' COMMENT '拒绝原因',
  `audit_time` datetime DEFAULT NULL COMMENT '审核时间',
  `audit_admin_id` int(11) unsigned DEFAULT '0' COMMENT '审核管理员ID',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  KEY `status` (`status`),
  KEY `create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='跑腿员认证表';

-- ========================================================
-- 7. 系统设置表
-- ========================================================
DROP TABLE IF EXISTS `settings`;
CREATE TABLE `settings` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '设置ID',
  `key` varchar(50) NOT NULL DEFAULT '' COMMENT '设置键',
  `value` text COMMENT '设置值',
  `group` varchar(50) DEFAULT '' COMMENT '分组',
  `description` varchar(255) DEFAULT '' COMMENT '描述',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `key` (`key`),
  KEY `group` (`group`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统设置表';

-- 插入默认设置
INSERT INTO `settings` (`key`, `value`, `group`, `description`) VALUES
('app_name', 'EXHome', 'basic', '应用名称'),
('app_logo', '/uploads/logo.png', 'basic', '应用Logo'),
('service_phone', '400-888-8888', 'basic', '客服电话'),
('order_base_fee', '10', 'order', '订单基础费用(元)'),
('order_base_count', '5', 'order', '基础包含快递件数'),
('order_package_fee', '2', 'order', '超出件数费用(元/件)'),
('order_base_weight', '2.5', 'order', '基础包含重量(kg)'),
('order_weight_fee', '2', 'order', '超出重量费用(元/kg)'),
('order_urgency_fee', '5', 'order', '加急服务费用(元)'),
('wx_appid', '', 'wx', '微信小程序AppID'),
('wx_secret', '', 'wx', '微信小程序AppSecret'),
('wx_mchid', '', 'wx', '微信支付商户号'),
('wx_pay_key', '', 'wx', '微信支付API密钥'),
('wx_pay_notify', '', 'wx', '微信支付回调地址'),
('wx_pay_cert_path', '', 'wx', '微信支付证书路径(服务器绝对路径)'),
('wx_pay_key_path', '', 'wx', '微信支付证书密钥路径(服务器绝对路径)'),
('alipay_appid', '', 'alipay', '支付宝应用AppID'),
('alipay_private_key', '', 'alipay', '支付宝应用私钥'),
('alipay_public_key', '', 'alipay', '支付宝公钥'),
('alipay_notify', '', 'alipay', '支付宝支付回调地址');

-- ========================================================
-- 8. 轮播图表
-- ========================================================
DROP TABLE IF EXISTS `banners`;
CREATE TABLE `banners` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '轮播图ID',
  `title` varchar(100) NOT NULL DEFAULT '' COMMENT '标题',
  `image` varchar(255) NOT NULL DEFAULT '' COMMENT '图片URL',
  `link` varchar(255) DEFAULT '' COMMENT '链接地址',
  `sort` int(11) NOT NULL DEFAULT '0' COMMENT '排序(越大越靠前)',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '状态(0=禁用,1=启用)',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `status` (`status`),
  KEY `sort` (`sort`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='轮播图表';

-- ========================================================
-- 9. 公告表
-- ========================================================
DROP TABLE IF EXISTS `notices`;
CREATE TABLE `notices` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '公告ID',
  `title` varchar(200) NOT NULL DEFAULT '' COMMENT '标题',
  `content` text COMMENT '内容',
  `is_top` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否置顶(0=否,1=是)',
  `view_count` int(11) NOT NULL DEFAULT '0' COMMENT '浏览次数',
  `status` tinyint(1) NOT NULL DEFAULT '1' COMMENT '状态(0=禁用,1=启用)',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `is_top` (`is_top`),
  KEY `status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公告表';

-- ========================================================
-- 10. 提现申请表
-- ========================================================
DROP TABLE IF EXISTS `withdrawals`;
CREATE TABLE `withdrawals` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '提现ID',
  `user_id` int(11) unsigned NOT NULL DEFAULT '0' COMMENT '用户ID',
  `amount` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '提现金额',
  `fee` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '手续费',
  `actual_amount` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '实际到账金额',
  `status` tinyint(1) NOT NULL DEFAULT '0' COMMENT '状态(0=待审核,1=已通过,2=已拒绝,3=已打款)',
  `reject_reason` varchar(255) DEFAULT '' COMMENT '拒绝原因',
  `audit_time` datetime DEFAULT NULL COMMENT '审核时间',
  `audit_admin_id` int(11) unsigned DEFAULT '0' COMMENT '审核管理员ID',
  `pay_time` datetime DEFAULT NULL COMMENT '打款时间',
  `pay_trade_no` varchar(100) DEFAULT '' COMMENT '支付流水号',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `status` (`status`),
  KEY `create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提现申请表';

-- ========================================================
-- 11. 用户余额变动记录表
-- ========================================================
DROP TABLE IF EXISTS `balance_logs`;
CREATE TABLE `balance_logs` (
  `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '记录ID',
  `user_id` int(11) unsigned NOT NULL DEFAULT '0' COMMENT '用户ID',
  `type` tinyint(1) NOT NULL DEFAULT '1' COMMENT '类型(1=收入,2=支出)',
  `amount` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '变动金额',
  `before_balance` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '变动前余额',
  `after_balance` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '变动后余额',
  `source` varchar(50) DEFAULT '' COMMENT '来源(order=订单,withdraw=提现,recharge=充值,refund=退款)',
  `source_id` int(11) unsigned DEFAULT '0' COMMENT '来源ID',
  `related_id` int(11) unsigned DEFAULT '0' COMMENT '关联ID(如订单ID)',
  `remark` varchar(255) DEFAULT '' COMMENT '备注',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `type` (`type`),
  KEY `source` (`source`),
  KEY `create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户余额变动记录表';

SET FOREIGN_KEY_CHECKS = 1;
