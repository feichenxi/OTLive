-- 删除 voice_prompt 字段的 SQL
-- 请在执行前备份数据库

-- 删除 voice 表中的 voice_prompt 字段
ALTER TABLE `voice` DROP COLUMN `voice_prompt`;
