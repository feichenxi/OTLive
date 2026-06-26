-- phpMyAdmin SQL Dump
-- version 5.1.1
-- https://www.phpmyadmin.net/
--
-- 主机： localhost
-- 生成日期： 2026-03-05 22:59:09
-- 服务器版本： 5.7.44-log
-- PHP 版本： 7.3.32

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- 数据库： `live`
--

-- --------------------------------------------------------

--
-- 表的结构 `license`
--

CREATE TABLE `license` (
  `id` int(11) NOT NULL COMMENT '主键ID',
  `machine_code` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '机器码(MD5)',
  `machine_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '机器名称(备注)',
  `customer_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '客户名称',
  `expire_date` date NOT NULL COMMENT '授权到期日期',
  `license_type` enum('trial','monthly','yearly','permanent') COLLATE utf8mb4_unicode_ci DEFAULT 'monthly' COMMENT '授权类型',
  `max_rooms` int(11) DEFAULT '12' COMMENT '最大房间数限制',
  `features` json DEFAULT NULL COMMENT '功能权限配置(JSON)',
  `status` tinyint(4) DEFAULT '1' COMMENT '状态: 0=禁用 1=启用',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `last_verify_at` datetime DEFAULT NULL COMMENT '最后验证时间',
  `verify_count` int(11) DEFAULT '0' COMMENT '验证次数',
  `remark` text COLLATE utf8mb4_unicode_ci COMMENT '备注'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统授权表';

--
-- 转储表的索引
--

--
-- 表的索引 `license`
--
ALTER TABLE `license`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `machine_code` (`machine_code`),
  ADD KEY `idx_machine_code` (`machine_code`),
  ADD KEY `idx_status` (`status`),
  ADD KEY `idx_expire_date` (`expire_date`);

--
-- 在导出的表使用AUTO_INCREMENT
--

--
-- 使用表AUTO_INCREMENT `license`
--
ALTER TABLE `license`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID';
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
