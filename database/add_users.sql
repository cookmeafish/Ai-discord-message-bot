-- ============================================
-- ADD USERS AND NICKNAMES TO DATABASE
-- For "Mistel Fiech's server" Database
-- ============================================
--
-- This file populates the users and nicknames tables with
-- the 10 users from the bot identity migration.
--
-- Execute this BEFORE importing long_term_memory data
-- to satisfy foreign key constraints.
-- ============================================

-- ============================================
-- STEP 1: INSERT USERS
-- ============================================

INSERT OR REPLACE INTO users (user_id, first_seen, last_seen) VALUES
(541286008738807811, datetime('now'), datetime('now')),   -- Zekke
(978458030079348797, datetime('now'), datetime('now')),   -- Csama
(1395983671747678333, datetime('now'), datetime('now')),  -- Anya Sama
(968980122440970252, datetime('now'), datetime('now')),   -- Mr. Fish
(1015896610556878938, datetime('now'), datetime('now')),  -- NakiiMirai
(819014744840339476, datetime('now'), datetime('now')),   -- Racoon
(1049532657714855976, datetime('now'), datetime('now')),  -- Angel Yamazaki
(1022420899091189760, datetime('now'), datetime('now')),  -- Zone
(1427471452805795885, datetime('now'), datetime('now')),  -- Mio
(1131391488257966131, datetime('now'), datetime('now'));  -- Tripalow

-- ============================================
-- STEP 2: INSERT NICKNAMES
-- ============================================

-- Zekke (541286008738807811)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(541286008738807811, 'Zekke', datetime('now')),
(541286008738807811, 'Zekkekun', datetime('now'));

-- Csama (978458030079348797)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(978458030079348797, 'Csama', datetime('now'));

-- Anya Sama (1395983671747678333)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(1395983671747678333, 'Anya Sama', datetime('now')),
(1395983671747678333, 'Mango', datetime('now')),
(1395983671747678333, 'Akitruh', datetime('now'));

-- Mr. Fish (968980122440970252)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(968980122440970252, 'Mr. Fish', datetime('now')),
(968980122440970252, 'Handsome Lad', datetime('now')),
(968980122440970252, 'cookmeafish', datetime('now')),
(968980122440970252, 'Mistel Fiech', datetime('now'));

-- NakiiMirai (1015896610556878938)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(1015896610556878938, 'NakiiMirai', datetime('now'));

-- Racoon (819014744840339476)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(819014744840339476, 'Racoon', datetime('now')),
(819014744840339476, 'Racooninabush', datetime('now'));

-- Angel Yamazaki (1049532657714855976)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(1049532657714855976, 'Angel Yamazaki', datetime('now'));

-- Zone (1022420899091189760)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(1022420899091189760, 'Zone', datetime('now'));

-- Mio (1427471452805795885)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(1427471452805795885, 'Mio', datetime('now')),
(1427471452805795885, 'Paimon', datetime('now')),
(1427471452805795885, 'Mionkey', datetime('now'));

-- Tripalow (1131391488257966131)
INSERT INTO nicknames (user_id, nickname, timestamp) VALUES
(1131391488257966131, 'Tripalow', datetime('now'));

-- ============================================
-- IMPORT COMPLETE
-- ============================================
--
-- Next steps:
-- 1. Connect to the "Mistel Fiech's server" database
-- 2. Execute this SQL file
-- 3. Verify entries:
--    SELECT * FROM users;
--    SELECT * FROM nicknames;
-- 4. Then proceed with import_old_bot_facts.sql
--
-- Database path: database/Mistel Fiech's server_data.db
-- ============================================
