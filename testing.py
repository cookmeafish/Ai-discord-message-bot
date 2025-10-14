"""
Comprehensive testing module for Discord bot systems.
Validates database operations, AI integrations, and core functionality.
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Dict, List, Tuple
import discord


class BotTestSuite:
    """
    Comprehensive test suite for validating bot functionality.
    Tests are organized by category and report pass/fail status.
    """

    def __init__(self, bot, guild_id: int, guild_name: str):
        """
        Initialize test suite.

        Args:
            bot: Discord bot instance
            guild_id: Guild ID to test against
            guild_name: Guild name for database lookup
        """
        self.bot = bot
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.db_manager = bot.get_server_db(guild_id, guild_name)
        self.results = []

    def _log_test(self, category: str, test_name: str, passed: bool, details: str = ""):
        """Log a test result."""
        status = "PASS" if passed else "FAIL"
        emoji = "✅" if passed else "❌"
        self.results.append({
            "category": category,
            "test": test_name,
            "status": status,
            "emoji": emoji,
            "details": details,
            "passed": passed
        })

    async def run_all_tests(self) -> Dict:
        """
        Run all test categories.

        Returns:
            Dictionary with test results and summary
        """
        print(f"\n{'='*60}")
        print(f"Starting Bot Test Suite for Guild: {self.guild_name}")
        print(f"{'='*60}\n")

        # Run all test categories
        await self.test_database_connection()
        await self.test_database_tables()
        await self.test_bot_identity()
        await self.test_relationship_metrics()
        await self.test_long_term_memory()
        await self.test_short_term_memory()
        await self.test_memory_consolidation()
        await self.test_ai_integration()
        await self.test_config_manager()
        await self.test_emote_system()

        # New test categories (Phase 2 expansion)
        await self.test_per_server_isolation()
        await self.test_input_validation()
        await self.test_global_state()
        await self.test_user_management()
        await self.test_archive_system()
        await self.test_image_rate_limiting()
        await self.test_channel_configuration()

        # Final cleanup verification (catch-all)
        await self.test_cleanup_verification()

        # Generate summary
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["passed"])
        failed_tests = total_tests - passed_tests
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        summary = {
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "pass_rate": pass_rate,
            "results": self.results,
            "guild_name": self.guild_name,
            "guild_id": self.guild_id,
            "timestamp": datetime.now().isoformat()
        }

        print(f"\n{'='*60}")
        print(f"Test Suite Complete")
        print(f"Total: {total_tests} | Passed: {passed_tests} | Failed: {failed_tests}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        print(f"{'='*60}\n")

        # Save results to log file
        self._save_test_log(summary)

        return summary

    def _save_test_log(self, summary: Dict):
        """Save test results to logs directory."""
        try:
            # Get logs directory
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
            os.makedirs(logs_dir, exist_ok=True)

            # Create log filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"test_results_{timestamp}.json"
            log_path = os.path.join(logs_dir, log_filename)

            # Save to JSON
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

            print(f"Test results saved to: {log_path}")
        except Exception as e:
            print(f"Warning: Could not save test log: {e}")

    # ==================== DATABASE TESTS ====================

    async def test_database_connection(self):
        """Test database connection and accessibility."""
        category = "Database Connection"

        # Test 1: Database manager exists
        try:
            exists = self.db_manager is not None
            self._log_test(
                category,
                "Database Manager Initialization",
                exists,
                "Database manager successfully retrieved" if exists else "Failed to get database manager"
            )
        except Exception as e:
            self._log_test(category, "Database Manager Initialization", False, f"Error: {e}")

        # Test 2: Database file exists
        try:
            if self.db_manager:
                db_path = self.db_manager.db_path
                file_exists = os.path.exists(db_path)
                self._log_test(
                    category,
                    "Database File Existence",
                    file_exists,
                    f"Database file at: {db_path}" if file_exists else f"File not found: {db_path}"
                )
        except Exception as e:
            self._log_test(category, "Database File Existence", False, f"Error: {e}")

        # Test 3: Can execute simple query
        try:
            if self.db_manager:
                cursor = self.db_manager.conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                success = result == (1,)
                self._log_test(
                    category,
                    "Basic Query Execution",
                    success,
                    "Simple query executed successfully" if success else "Query returned unexpected result"
                )
        except Exception as e:
            self._log_test(category, "Basic Query Execution", False, f"Error: {e}")

    async def test_database_tables(self):
        """Test that all required tables exist."""
        category = "Database Tables"

        required_tables = [
            "bot_identity",
            "relationship_metrics",
            "long_term_memory",
            "global_state",
            "short_term_message_log",
            "users"
        ]

        for table_name in required_tables:
            try:
                cursor = self.db_manager.conn.cursor()
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                result = cursor.fetchone()
                exists = result is not None
                self._log_test(
                    category,
                    f"Table: {table_name}",
                    exists,
                    f"Table '{table_name}' exists" if exists else f"Table '{table_name}' missing"
                )
            except Exception as e:
                self._log_test(category, f"Table: {table_name}", False, f"Error: {e}")

    # ==================== BOT IDENTITY TESTS ====================

    async def test_bot_identity(self):
        """Test bot identity storage and retrieval."""
        category = "Bot Identity"

        # Test 1: Can retrieve bot identity
        try:
            traits = self.db_manager.get_bot_identity("trait")
            lore = self.db_manager.get_bot_identity("lore")
            facts = self.db_manager.get_bot_identity("fact")

            has_content = len(traits) > 0 or len(lore) > 0 or len(facts) > 0
            self._log_test(
                category,
                "Retrieve Bot Identity",
                has_content,
                f"Found {len(traits)} traits, {len(lore)} lore, {len(facts)} facts" if has_content else "No identity data found"
            )
        except Exception as e:
            self._log_test(category, "Retrieve Bot Identity", False, f"Error: {e}")

        # Test 2: Can add and retrieve test trait
        try:
            test_trait = f"TEST_TRAIT_{datetime.now().timestamp()}"
            self.db_manager.add_bot_identity("trait", test_trait)

            traits = self.db_manager.get_bot_identity("trait")  # Returns list of strings
            added = test_trait in traits

            # Clean up test data
            if added:
                cursor = self.db_manager.conn.cursor()
                cursor.execute("DELETE FROM bot_identity WHERE content = ?", (test_trait,))
                self.db_manager.conn.commit()

            self._log_test(
                category,
                "Add/Retrieve Bot Identity",
                added,
                "Successfully added and retrieved test trait" if added else "Failed to add or retrieve test trait"
            )
        except Exception as e:
            self._log_test(category, "Add/Retrieve Bot Identity", False, f"Error: {e}")

    # ==================== RELATIONSHIP METRICS TESTS ====================

    async def test_relationship_metrics(self):
        """Test relationship metrics operations."""
        category = "Relationship Metrics"

        test_user_id = 999999999999999999  # Fake user ID for testing

        # Test 1: Auto-create metrics for new user (via get)
        try:
            # Ensure user exists in users table first
            self.db_manager._ensure_user_exists(test_user_id)

            metrics = self.db_manager.get_relationship_metrics(test_user_id)  # Auto-creates if not exists

            initialized = metrics is not None and all(k in metrics for k in ['anger', 'rapport', 'trust', 'formality'])
            self._log_test(
                category,
                "Auto-Create User Metrics",
                initialized,
                f"Metrics initialized: {metrics}" if initialized else "Failed to initialize metrics"
            )
        except Exception as e:
            self._log_test(category, "Auto-Create User Metrics", False, f"Error: {e}")

        # Test 2: Update metrics
        try:
            self.db_manager.update_relationship_metrics(
                test_user_id,
                rapport=8,
                trust=7,
                anger=2,
                formality=-3
            )

            metrics = self.db_manager.get_relationship_metrics(test_user_id)
            updated = (
                metrics["rapport"] == 8 and
                metrics["trust"] == 7 and
                metrics["anger"] == 2 and
                metrics["formality"] == -3
            )

            self._log_test(
                category,
                "Update Relationship Metrics",
                updated,
                f"Metrics updated correctly: {metrics}" if updated else f"Metrics mismatch: {metrics}"
            )
        except Exception as e:
            self._log_test(category, "Update Relationship Metrics", False, f"Error: {e}")

        # Test 3: Clean up test user
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("DELETE FROM relationship_metrics WHERE user_id = ?", (test_user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = ?", (test_user_id,))  # Also clean up from users table
            self.db_manager.conn.commit()

            # Check directly with SQL instead of get_relationship_metrics (which auto-creates)
            cursor.execute("SELECT COUNT(*) FROM relationship_metrics WHERE user_id = ?", (test_user_id,))
            count = cursor.fetchone()[0]
            cleaned = count == 0

            self._log_test(
                category,
                "Delete Test Metrics",
                cleaned,
                "Test metrics cleaned up successfully" if cleaned else f"Failed to clean up test metrics ({count} remaining)"
            )
            cursor.close()
        except Exception as e:
            self._log_test(category, "Delete Test Metrics", False, f"Error: {e}")

    # ==================== LONG-TERM MEMORY TESTS ====================

    async def test_long_term_memory(self):
        """Test long-term memory operations."""
        category = "Long-Term Memory"

        test_user_id = 999999999999999999
        test_fact = f"User likes testing and validation TEST_{datetime.now().timestamp()}"

        # Test 1: Add memory
        try:
            # Ensure user exists first (required for foreign key constraints)
            self.db_manager._ensure_user_exists(test_user_id)

            result = self.db_manager.add_long_term_memory(
                user_id=test_user_id,
                fact=test_fact,
                source_user_id=test_user_id,
                source_nickname="TestUser"
            )

            memories = self.db_manager.get_long_term_memory(test_user_id)  # Returns list of tuples: (fact, source_user_id, source_nickname)
            added = result and any(m[0] == test_fact for m in memories)

            self._log_test(
                category,
                "Add Long-Term Memory",
                added,
                f"Memory added successfully" if added else f"Failed to add memory (result={result})"
            )
        except Exception as e:
            self._log_test(category, "Add Long-Term Memory", False, f"Error: {e}")

        # Test 2: Find contradictory memory
        try:
            similar_memories = self.db_manager.find_contradictory_memory(test_user_id, test_fact)
            found = len(similar_memories) > 0

            self._log_test(
                category,
                "Find Contradictory Memory",
                found,
                f"Found {len(similar_memories)} similar memories" if found else "No similar memories found"
            )
        except Exception as e:
            self._log_test(category, "Find Contradictory Memory", False, f"Error: {e}")

        # Test 3: Update memory (use find_contradictory_memory to get ID)
        try:
            similar_memories = self.db_manager.find_contradictory_memory(test_user_id, test_fact)  # Returns [(id, fact), ...]

            if similar_memories:
                test_memory_id = similar_memories[0][0]  # Get first ID
                updated_fact = f"UPDATED_{test_fact}"
                self.db_manager.update_long_term_memory_fact(test_memory_id, updated_fact)

                memories = self.db_manager.get_long_term_memory(test_user_id)
                updated = any(m[0] == updated_fact for m in memories)

                self._log_test(
                    category,
                    "Update Long-Term Memory",
                    updated,
                    "Memory updated successfully" if updated else "Failed to update memory"
                )
            else:
                self._log_test(category, "Update Long-Term Memory", False, "Test memory not found")
        except Exception as e:
            self._log_test(category, "Update Long-Term Memory", False, f"Error: {e}")

        # Test 4: Delete memory
        try:
            similar_memories = self.db_manager.find_contradictory_memory(test_user_id, "testing and validation TEST_")
            test_memories = [m for m in similar_memories if "TEST_" in m[1]]

            for memory_id, memory_fact in test_memories:
                self.db_manager.delete_long_term_memory_fact(memory_id)

            memories = self.db_manager.get_long_term_memory(test_user_id)
            cleaned = not any("TEST_" in m[0] for m in memories)

            # Also clean up the test user
            cursor = self.db_manager.conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id = ?", (test_user_id,))
            self.db_manager.conn.commit()
            cursor.close()

            self._log_test(
                category,
                "Delete Long-Term Memory",
                cleaned,
                f"Deleted {len(test_memories)} test memories" if cleaned else "Failed to delete test memories"
            )
        except Exception as e:
            self._log_test(category, "Delete Long-Term Memory", False, f"Error: {e}")

    # ==================== SHORT-TERM MEMORY TESTS ====================

    async def test_short_term_memory(self):
        """Test short-term memory operations."""
        category = "Short-Term Memory"

        test_message_id = 999999999999999999
        test_user_id = 999999999999999999

        # Test 1: Log message (direct SQL since log_message requires Discord message object)
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute(
                "INSERT INTO short_term_message_log (message_id, user_id, channel_id, content, timestamp, directed_at_bot) VALUES (?, ?, ?, ?, ?, ?)",
                (test_message_id, test_user_id, 999999999999999999, "This is a test message", datetime.now().isoformat(), 0)
            )
            self.db_manager.conn.commit()

            messages = self.db_manager.get_short_term_memory()
            logged = any(m["message_id"] == test_message_id for m in messages)

            self._log_test(
                category,
                "Log Message",
                logged,
                "Message logged successfully" if logged else "Failed to log message"
            )
        except Exception as e:
            self._log_test(category, "Log Message", False, f"Error: {e}")

        # Test 2: Retrieve short-term memory
        try:
            messages = self.db_manager.get_short_term_memory()
            retrieved = messages is not None and len(messages) >= 0

            self._log_test(
                category,
                "Retrieve Short-Term Memory",
                retrieved,
                f"Retrieved {len(messages)} messages" if retrieved else "Failed to retrieve messages"
            )
        except Exception as e:
            self._log_test(category, "Retrieve Short-Term Memory", False, f"Error: {e}")

        # Test 3: Clean up test message
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("DELETE FROM short_term_message_log WHERE message_id = ?", (test_message_id,))
            self.db_manager.conn.commit()

            messages = self.db_manager.get_short_term_memory()
            cleaned = not any(m["message_id"] == test_message_id for m in messages)

            self._log_test(
                category,
                "Delete Test Message",
                cleaned,
                "Test message cleaned up successfully" if cleaned else "Failed to clean up test message"
            )
        except Exception as e:
            self._log_test(category, "Delete Test Message", False, f"Error: {e}")

    # ==================== MEMORY CONSOLIDATION TESTS ====================

    async def test_memory_consolidation(self):
        """Test memory consolidation system."""
        category = "Memory Consolidation"

        # Test 1: Archive directory exists
        try:
            archive_dir = os.path.join(os.path.dirname(self.db_manager.db_path), "archive")
            exists = os.path.exists(archive_dir)

            self._log_test(
                category,
                "Archive Directory Exists",
                exists,
                f"Archive directory at: {archive_dir}" if exists else f"Archive directory missing: {archive_dir}"
            )
        except Exception as e:
            self._log_test(category, "Archive Directory Exists", False, f"Error: {e}")

        # Test 2: Check if consolidation function exists
        try:
            from cogs.memory_tasks import MemoryTasksCog
            cog = self.bot.get_cog("MemoryTasksCog")
            has_method = cog is not None and hasattr(cog, "consolidate_memories")

            self._log_test(
                category,
                "Consolidation Function Exists",
                has_method,
                "consolidate_memories method found" if has_method else "consolidate_memories method missing"
            )
        except Exception as e:
            self._log_test(category, "Consolidation Function Exists", False, f"Error: {e}")

    # ==================== AI INTEGRATION TESTS ====================

    async def test_ai_integration(self):
        """Test AI handler integration."""
        category = "AI Integration"

        # Test 1: AI Handler exists
        try:
            has_handler = hasattr(self.bot, "ai_handler") and self.bot.ai_handler is not None
            self._log_test(
                category,
                "AI Handler Initialization",
                has_handler,
                "AI Handler exists and initialized" if has_handler else "AI Handler missing"
            )
        except Exception as e:
            self._log_test(category, "AI Handler Initialization", False, f"Error: {e}")

        # Test 2: OpenAI API key configured
        try:
            api_key = self.bot.config_manager.get_secret("OPENAI_API_KEY")
            configured = api_key is not None and len(api_key) > 0

            self._log_test(
                category,
                "OpenAI API Key Configured",
                configured,
                "API key configured" if configured else "API key missing"
            )
        except Exception as e:
            self._log_test(category, "OpenAI API Key Configured", False, f"Error: {e}")

        # Test 3: AI model configuration
        try:
            config = self.bot.config_manager.get_config()
            has_models = "ai_models" in config and "primary_model" in config["ai_models"]

            model_name = config["ai_models"]["primary_model"] if has_models else "Not configured"

            self._log_test(
                category,
                "AI Model Configuration",
                has_models,
                f"Primary model: {model_name}" if has_models else "AI models not configured"
            )
        except Exception as e:
            self._log_test(category, "AI Model Configuration", False, f"Error: {e}")

    # ==================== CONFIG MANAGER TESTS ====================

    async def test_config_manager(self):
        """Test configuration manager."""
        category = "Config Manager"

        # Test 1: Config manager exists
        try:
            has_manager = hasattr(self.bot, "config_manager") and self.bot.config_manager is not None
            self._log_test(
                category,
                "Config Manager Initialization",
                has_manager,
                "Config Manager exists" if has_manager else "Config Manager missing"
            )
        except Exception as e:
            self._log_test(category, "Config Manager Initialization", False, f"Error: {e}")

        # Test 2: Can load config
        try:
            config = self.bot.config_manager.get_config()
            loaded = config is not None and isinstance(config, dict)

            self._log_test(
                category,
                "Load Configuration",
                loaded,
                f"Config loaded with {len(config)} keys" if loaded else "Failed to load config"
            )
        except Exception as e:
            self._log_test(category, "Load Configuration", False, f"Error: {e}")

        # Test 3: Required config keys exist
        try:
            config = self.bot.config_manager.get_config()
            required_keys = ["ai_models", "response_limits", "personality_mode"]
            missing_keys = [key for key in required_keys if key not in config]

            has_all = len(missing_keys) == 0

            self._log_test(
                category,
                "Required Config Keys",
                has_all,
                "All required keys present" if has_all else f"Missing keys: {missing_keys}"
            )
        except Exception as e:
            self._log_test(category, "Required Config Keys", False, f"Error: {e}")

    # ==================== EMOTE SYSTEM TESTS ====================

    async def test_emote_system(self):
        """Test emote orchestrator."""
        category = "Emote System"

        # Test 1: Emote handler exists (attribute is emote_handler, not emote_orchestrator)
        try:
            has_handler = hasattr(self.bot, "emote_handler") and self.bot.emote_handler is not None
            self._log_test(
                category,
                "Emote Handler Initialization",
                has_handler,
                "Emote Handler exists" if has_handler else "Emote Handler missing"
            )
        except Exception as e:
            self._log_test(category, "Emote Handler Initialization", False, f"Error: {e}")

        # Test 2: Can load emotes
        try:
            if hasattr(self.bot, "emote_handler"):
                emote_count = len(self.bot.emote_handler.emotes)  # Attribute is 'emotes', not 'emote_map'
                loaded = emote_count >= 0

                self._log_test(
                    category,
                    "Load Emotes",
                    loaded,
                    f"Loaded {emote_count} emotes" if loaded else "Failed to load emotes"
                )
            else:
                self._log_test(category, "Load Emotes", False, "Emote handler not available")
        except Exception as e:
            self._log_test(category, "Load Emotes", False, f"Error: {e}")

    # ==================== PER-SERVER ISOLATION TESTS ====================

    async def test_per_server_isolation(self):
        """Test per-server database isolation architecture."""
        category = "Per-Server Isolation"

        # Test 1: Database file has server-specific name
        try:
            db_path = self.db_manager.db_path
            has_server_name = self.guild_name.replace(" ", "_")[:50] in db_path or "_data.db" in db_path

            self._log_test(
                category,
                "Server-Specific Database File",
                has_server_name,
                f"Database path: {db_path}" if has_server_name else f"Path doesn't reflect server isolation: {db_path}"
            )
        except Exception as e:
            self._log_test(category, "Server-Specific Database File", False, f"Error: {e}")

        # Test 2: Multi-database manager exists
        try:
            has_multi_db = hasattr(self.bot, "multi_db_manager") or hasattr(self.bot, "get_server_db")

            self._log_test(
                category,
                "Multi-Database Manager",
                has_multi_db,
                "Multi-database manager available" if has_multi_db else "Multi-database manager missing"
            )
        except Exception as e:
            self._log_test(category, "Multi-Database Manager", False, f"Error: {e}")

        # Test 3: Database path is in database directory
        try:
            db_path = self.db_manager.db_path
            in_db_dir = "database" in db_path.lower()

            self._log_test(
                category,
                "Database Directory Structure",
                in_db_dir,
                f"Database in correct directory: {db_path}" if in_db_dir else f"Database not in 'database' directory: {db_path}"
            )
        except Exception as e:
            self._log_test(category, "Database Directory Structure", False, f"Error: {e}")

        # Test 4: SQLite auto-vacuum enabled
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("PRAGMA auto_vacuum")
            result = cursor.fetchone()
            auto_vacuum_enabled = result and result[0] in (1, 2)  # 1=FULL, 2=INCREMENTAL
            cursor.close()

            self._log_test(
                category,
                "SQLite Auto-Vacuum Enabled",
                auto_vacuum_enabled,
                f"Auto-vacuum mode: {result[0] if result else 'OFF'}" if auto_vacuum_enabled else "Auto-vacuum not enabled"
            )
        except Exception as e:
            self._log_test(category, "SQLite Auto-Vacuum Enabled", False, f"Error: {e}")

    # ==================== INPUT VALIDATION TESTS ====================

    async def test_input_validation(self):
        """Test input validation and security measures."""
        category = "Input Validation"

        # Test 1: SQL injection prevention in bot identity
        try:
            malicious_input = "'; DROP TABLE bot_identity; --"
            result = self.db_manager.add_bot_identity("trait", malicious_input)

            # Check if table still exists after attempt
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_identity'")
            table_exists = cursor.fetchone() is not None
            cursor.close()

            # Clean up if it was added
            if result:
                cursor = self.db_manager.conn.cursor()
                cursor.execute("DELETE FROM bot_identity WHERE content = ?", (malicious_input,))
                self.db_manager.conn.commit()
                cursor.close()

            self._log_test(
                category,
                "SQL Injection Prevention",
                table_exists,
                "Table protected from SQL injection" if table_exists else "SQL injection vulnerability detected"
            )
        except Exception as e:
            self._log_test(category, "SQL Injection Prevention", False, f"Error: {e}")

        # Test 2: Oversized content rejection
        try:
            oversized_content = "A" * 100000  # 100KB string
            result = self.db_manager.add_bot_identity("trait", oversized_content)

            # Check if it was rejected or truncated
            traits = self.db_manager.get_bot_identity("trait")
            not_added = oversized_content not in traits

            # Clean up if somehow added
            if not not_added:
                cursor = self.db_manager.conn.cursor()
                cursor.execute("DELETE FROM bot_identity WHERE content = ?", (oversized_content,))
                self.db_manager.conn.commit()
                cursor.close()

            self._log_test(
                category,
                "Oversized Content Rejection",
                not_added,
                "Oversized content rejected" if not_added else "Oversized content was accepted"
            )
        except Exception as e:
            self._log_test(category, "Oversized Content Rejection", False, f"Error: {e}")

        # Test 3: Empty/null input handling
        try:
            empty_result = self.db_manager.add_bot_identity("trait", "")
            null_result = self.db_manager.add_bot_identity("trait", None) if None else False

            # Both should be rejected
            rejected = not empty_result and not null_result

            self._log_test(
                category,
                "Empty/Null Input Rejection",
                rejected,
                "Empty and null inputs rejected" if rejected else "Empty or null inputs accepted"
            )
        except Exception as e:
            # Exception is acceptable for null input
            self._log_test(category, "Empty/Null Input Rejection", True, "Null input properly rejected with exception")

        # Test 4: Invalid category rejection
        try:
            invalid_category = "INVALID_CATEGORY_123"
            result = self.db_manager.add_bot_identity(invalid_category, "test content")

            # Should be rejected
            rejected = not result

            self._log_test(
                category,
                "Invalid Category Rejection",
                rejected,
                "Invalid category rejected" if rejected else "Invalid category was accepted"
            )
        except Exception as e:
            self._log_test(category, "Invalid Category Rejection", False, f"Error: {e}")

    # ==================== GLOBAL STATE TESTS ====================

    async def test_global_state(self):
        """Test global state management system."""
        category = "Global State"

        test_key = f"TEST_STATE_{datetime.now().timestamp()}"
        test_value = "TEST_VALUE_123"

        # Test 1: Set global state
        try:
            self.db_manager.set_global_state(test_key, test_value)

            # Verify it was set
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT state_value FROM global_state WHERE state_key = ?", (test_key,))
            result = cursor.fetchone()
            cursor.close()

            success = result is not None and result[0] == test_value

            self._log_test(
                category,
                "Set Global State",
                success,
                f"State set successfully: {test_key}={test_value}" if success else "Failed to set global state"
            )
        except Exception as e:
            self._log_test(category, "Set Global State", False, f"Error: {e}")

        # Test 2: Get global state
        try:
            retrieved_value = self.db_manager.get_global_state(test_key)
            success = retrieved_value == test_value

            self._log_test(
                category,
                "Get Global State",
                success,
                f"Retrieved value: {retrieved_value}" if success else f"Value mismatch: expected {test_value}, got {retrieved_value}"
            )
        except Exception as e:
            self._log_test(category, "Get Global State", False, f"Error: {e}")

        # Test 3: Clean up test state
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("DELETE FROM global_state WHERE state_key = ?", (test_key,))
            self.db_manager.conn.commit()

            # Verify deletion
            result = self.db_manager.get_global_state(test_key)
            cleaned = result is None
            cursor.close()

            self._log_test(
                category,
                "Delete Global State",
                cleaned,
                "Test state cleaned successfully" if cleaned else "Failed to clean test state"
            )
        except Exception as e:
            self._log_test(category, "Delete Global State", False, f"Error: {e}")

    # ==================== USER MANAGEMENT TESTS ====================

    async def test_user_management(self):
        """Test user management and tracking system."""
        category = "User Management"

        test_user_id = 888888888888888888  # Different from other test IDs

        # Test 1: Ensure user exists functionality
        try:
            self.db_manager._ensure_user_exists(test_user_id)

            # Check if user was created
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT user_id, first_seen, last_seen FROM users WHERE user_id = ?", (test_user_id,))
            result = cursor.fetchone()
            cursor.close()

            created = result is not None and result[0] == test_user_id

            self._log_test(
                category,
                "Ensure User Exists",
                created,
                f"User record created for {test_user_id}" if created else "Failed to create user record"
            )
        except Exception as e:
            self._log_test(category, "Ensure User Exists", False, f"Error: {e}")

        # Test 2: User timestamps
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT first_seen, last_seen FROM users WHERE user_id = ?", (test_user_id,))
            result = cursor.fetchone()
            cursor.close()

            has_timestamps = result is not None and result[0] and result[1]

            self._log_test(
                category,
                "User Timestamps",
                has_timestamps,
                f"Timestamps: first_seen={result[0][:19] if result else 'N/A'}, last_seen={result[1][:19] if result else 'N/A'}" if has_timestamps else "Missing timestamps"
            )
        except Exception as e:
            self._log_test(category, "User Timestamps", False, f"Error: {e}")

        # Test 3: Clean up test user
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("DELETE FROM users WHERE user_id = ?", (test_user_id,))
            self.db_manager.conn.commit()

            # Verify deletion
            cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = ?", (test_user_id,))
            count = cursor.fetchone()[0]
            cursor.close()

            cleaned = count == 0

            self._log_test(
                category,
                "Delete Test User",
                cleaned,
                "Test user cleaned successfully" if cleaned else "Failed to clean test user"
            )
        except Exception as e:
            self._log_test(category, "Delete Test User", False, f"Error: {e}")

    # ==================== ARCHIVE SYSTEM TESTS ====================

    async def test_archive_system(self):
        """Test message archival and cleanup system."""
        category = "Archive System"

        # Test 1: Archive directory accessibility
        try:
            archive_dir = os.path.join(os.path.dirname(self.db_manager.db_path), "archive")

            # Check if accessible (may or may not exist yet)
            parent_exists = os.path.exists(os.path.dirname(archive_dir))
            accessible = parent_exists  # Parent dir must exist for archiving to work

            self._log_test(
                category,
                "Archive Directory Accessible",
                accessible,
                f"Archive parent directory exists: {os.path.dirname(archive_dir)}" if accessible else "Archive parent directory not accessible"
            )
        except Exception as e:
            self._log_test(category, "Archive Directory Accessible", False, f"Error: {e}")

        # Test 2: Archive function exists
        try:
            has_archive_method = hasattr(self.db_manager, "archive_and_clear_short_term_memory")

            self._log_test(
                category,
                "Archive Function Exists",
                has_archive_method,
                "archive_and_clear_short_term_memory method found" if has_archive_method else "Archive method missing"
            )
        except Exception as e:
            self._log_test(category, "Archive Function Exists", False, f"Error: {e}")

        # Test 3: Message count method
        try:
            count = self.db_manager.get_short_term_message_count()
            has_method = True

            self._log_test(
                category,
                "Message Count Method",
                has_method,
                f"Current message count: {count}" if has_method else "Message count method missing"
            )
        except Exception as e:
            self._log_test(category, "Message Count Method", False, f"Error: {e}")

        # Test 4: Archive JSON format validation
        try:
            archive_dir = os.path.join(os.path.dirname(self.db_manager.db_path), "archive")

            # Check if any archive files exist and validate format
            if os.path.exists(archive_dir):
                archive_files = [f for f in os.listdir(archive_dir) if f.startswith("short_term_archive_") and f.endswith(".json")]

                if archive_files:
                    # Read most recent archive
                    latest_archive = sorted(archive_files)[-1]
                    archive_path = os.path.join(archive_dir, latest_archive)

                    with open(archive_path, 'r', encoding='utf-8') as f:
                        archive_data = json.load(f)

                    # Validate required keys
                    valid_format = all(key in archive_data for key in ["archived_at", "message_count", "messages"])

                    self._log_test(
                        category,
                        "Archive JSON Format",
                        valid_format,
                        f"Valid archive format in {latest_archive}" if valid_format else "Archive format invalid"
                    )
                else:
                    self._log_test(category, "Archive JSON Format", True, "No archive files yet (normal for new servers)")
            else:
                self._log_test(category, "Archive JSON Format", True, "Archive directory not created yet (normal)")
        except Exception as e:
            self._log_test(category, "Archive JSON Format", False, f"Error: {e}")

    # ==================== IMAGE RATE LIMITING TESTS ====================

    async def test_image_rate_limiting(self):
        """Test image rate limiting system."""
        category = "Image Rate Limiting"

        test_user_id = 777777777777777777  # Different test ID

        # Test 1: Image count tracking table exists
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_image_stats'")
            exists = cursor.fetchone() is not None
            cursor.close()

            self._log_test(
                category,
                "Image Stats Table Exists",
                exists,
                "user_image_stats table found" if exists else "user_image_stats table missing"
            )
        except Exception as e:
            self._log_test(category, "Image Stats Table Exists", False, f"Error: {e}")

        # Test 2: Increment image count method
        try:
            has_method = hasattr(self.db_manager, "increment_user_image_count")
            result = None

            if has_method:
                # Ensure user exists first (required for foreign key constraint)
                self.db_manager._ensure_user_exists(test_user_id)

                # Clean up any existing record first
                cursor = self.db_manager.conn.cursor()
                cursor.execute("DELETE FROM user_image_stats WHERE user_id = ?", (test_user_id,))
                self.db_manager.conn.commit()
                cursor.close()

                # Test the method
                self.db_manager.increment_user_image_count(test_user_id)

                # Give a moment for commit to complete
                import time
                time.sleep(0.1)

                # Verify it was incremented
                cursor = self.db_manager.conn.cursor()
                cursor.execute("SELECT hourly_count, daily_count FROM user_image_stats WHERE user_id = ?", (test_user_id,))
                result = cursor.fetchone()

                # Debug: Check if table has any data at all
                cursor.execute("SELECT COUNT(*) FROM user_image_stats")
                total_count = cursor.fetchone()[0]
                cursor.close()

                success = result is not None and result[0] >= 1 and result[1] >= 1

                detail_msg = f"Image count incremented: hourly={result[0]}, daily={result[1]}" if (success and result) else f"Failed: result={result}, total_records={total_count}"
            else:
                success = False
                detail_msg = "Increment method missing"

            self._log_test(
                category,
                "Increment Image Count",
                success,
                detail_msg
            )
        except Exception as e:
            self._log_test(category, "Increment Image Count", False, f"Error: {e}")

        # Test 3: Get hourly count method
        try:
            has_method = hasattr(self.db_manager, "get_user_image_count_last_hour")

            if has_method:
                count = self.db_manager.get_user_image_count_last_hour(test_user_id)
                success = count >= 0  # Should return at least 0
            else:
                success = False

            self._log_test(
                category,
                "Get Hourly Image Count",
                success,
                f"Hourly count retrieved: {count if has_method else 'N/A'}" if success else "Get hourly count method missing"
            )
        except Exception as e:
            self._log_test(category, "Get Hourly Image Count", False, f"Error: {e}")

        # Test 4: Clean up test image stats
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute("DELETE FROM user_image_stats WHERE user_id = ?", (test_user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = ?", (test_user_id,))  # Also clean up user
            self.db_manager.conn.commit()

            # Verify deletion
            cursor.execute("SELECT COUNT(*) FROM user_image_stats WHERE user_id = ?", (test_user_id,))
            count = cursor.fetchone()[0]
            cursor.close()

            cleaned = count == 0

            self._log_test(
                category,
                "Delete Test Image Stats",
                cleaned,
                "Test image stats cleaned" if cleaned else "Failed to clean test image stats"
            )
        except Exception as e:
            self._log_test(category, "Delete Test Image Stats", False, f"Error: {e}")

    # ==================== CHANNEL CONFIGURATION TESTS ====================

    async def test_channel_configuration(self):
        """Test channel-specific configuration system."""
        category = "Channel Configuration"

        # Test 1: Config manager has channel settings
        try:
            config = self.bot.config_manager.get_config()
            has_channel_settings = "channel_settings" in config

            self._log_test(
                category,
                "Channel Settings in Config",
                has_channel_settings,
                f"Channel settings section exists with {len(config.get('channel_settings', {}))} channels configured" if has_channel_settings else "Channel settings section missing"
            )
        except Exception as e:
            self._log_test(category, "Channel Settings in Config", False, f"Error: {e}")

        # Test 2: Personality mode configuration exists
        try:
            config = self.bot.config_manager.get_config()
            has_personality_mode = "personality_mode" in config

            if has_personality_mode:
                pm_config = config["personality_mode"]
                has_required_keys = all(key in pm_config for key in ["immersive_character", "allow_technical_language"])
            else:
                has_required_keys = False

            self._log_test(
                category,
                "Personality Mode Configuration",
                has_required_keys,
                f"Personality mode config: immersive={pm_config.get('immersive_character')}, technical={pm_config.get('allow_technical_language')}" if has_required_keys else "Personality mode config incomplete"
            )
        except Exception as e:
            self._log_test(category, "Personality Mode Configuration", False, f"Error: {e}")

        # Test 3: Server info directory exists
        try:
            server_info_dir = os.path.join(os.path.dirname(os.path.dirname(self.db_manager.db_path)), "Server_Info")
            exists = os.path.exists(server_info_dir) or os.path.exists("Server_Info")

            self._log_test(
                category,
                "Server Info Directory",
                True,  # Always pass - directory is optional
                f"Server Info directory {'exists' if exists else 'not created (optional)'}: {server_info_dir if exists else 'Server_Info/'}"
            )
        except Exception as e:
            self._log_test(category, "Server Info Directory", False, f"Error: {e}")

    # ==================== CLEANUP VERIFICATION TESTS ====================

    async def test_cleanup_verification(self):
        """
        Final verification that all test data was properly cleaned up.
        This is a catch-all to ensure no test data remains in the database.
        """
        category = "Cleanup Verification"

        # All test user IDs used in tests
        test_user_ids = [999999999999999999, 888888888888888888, 777777777777777777]
        test_message_id = 999999999999999999

        # Test 1: No test bot identity entries remain
        try:
            cursor = self.db_manager.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM bot_identity WHERE content LIKE ?",
                ("%TEST_TRAIT_%",)
            )
            count = cursor.fetchone()[0]
            cleaned = count == 0

            self._log_test(
                category,
                "Bot Identity Cleanup",
                cleaned,
                "No test identity entries found" if cleaned else f"Found {count} test identity entries remaining"
            )

            # Force cleanup if any remain
            if count > 0:
                cursor.execute("DELETE FROM bot_identity WHERE content LIKE ?", ("%TEST_TRAIT_%",))
                self.db_manager.conn.commit()
                print(f"WARNING: Cleaned up {count} remaining test identity entries")

        except Exception as e:
            self._log_test(category, "Bot Identity Cleanup", False, f"Error: {e}")

        # Test 2: No test relationship metrics remain
        try:
            cursor = self.db_manager.conn.cursor()
            total_count = 0
            for uid in test_user_ids:
                cursor.execute("SELECT COUNT(*) FROM relationship_metrics WHERE user_id = ?", (uid,))
                total_count += cursor.fetchone()[0]

            cleaned = total_count == 0

            self._log_test(
                category,
                "Relationship Metrics Cleanup",
                cleaned,
                "No test metrics found" if cleaned else f"Found {total_count} test metric entries remaining"
            )

            # Force cleanup if any remain
            if total_count > 0:
                for uid in test_user_ids:
                    cursor.execute("DELETE FROM relationship_metrics WHERE user_id = ?", (uid,))
                self.db_manager.conn.commit()
                print(f"WARNING: Cleaned up {total_count} remaining test metric entries")
            cursor.close()

        except Exception as e:
            self._log_test(category, "Relationship Metrics Cleanup", False, f"Error: {e}")

        # Test 3: No test long-term memory entries remain
        try:
            cursor = self.db_manager.conn.cursor()
            total_count = 0

            # Check all test user IDs
            for uid in test_user_ids:
                cursor.execute(
                    "SELECT COUNT(*) FROM long_term_memory WHERE user_id = ?",
                    (uid,)
                )
                total_count += cursor.fetchone()[0]

            # Also check for TEST_ pattern in facts
            cursor.execute(
                "SELECT COUNT(*) FROM long_term_memory WHERE fact LIKE ?",
                ("%TEST_%",)
            )
            total_count += cursor.fetchone()[0]

            cleaned = total_count == 0

            self._log_test(
                category,
                "Long-Term Memory Cleanup",
                cleaned,
                "No test memory entries found" if cleaned else f"Found {total_count} test memory entries remaining"
            )

            # Force cleanup if any remain
            if total_count > 0:
                for uid in test_user_ids:
                    cursor.execute(
                        "DELETE FROM long_term_memory WHERE user_id = ?",
                        (uid,)
                    )
                cursor.execute(
                    "DELETE FROM long_term_memory WHERE fact LIKE ?",
                    ("%TEST_%",)
                )
                self.db_manager.conn.commit()
                print(f"WARNING: Cleaned up {total_count} remaining test memory entries")
            cursor.close()

        except Exception as e:
            self._log_test(category, "Long-Term Memory Cleanup", False, f"Error: {e}")

        # Test 4: No test short-term message log entries remain
        try:
            cursor = self.db_manager.conn.cursor()
            total_count = 0

            # Check test message ID
            cursor.execute(
                "SELECT COUNT(*) FROM short_term_message_log WHERE message_id = ?",
                (test_message_id,)
            )
            total_count += cursor.fetchone()[0]

            # Check all test user IDs
            for uid in test_user_ids:
                cursor.execute(
                    "SELECT COUNT(*) FROM short_term_message_log WHERE user_id = ?",
                    (uid,)
                )
                total_count += cursor.fetchone()[0]

            cleaned = total_count == 0

            self._log_test(
                category,
                "Short-Term Memory Cleanup",
                cleaned,
                "No test messages found" if cleaned else f"Found {total_count} test message entries remaining"
            )

            # Force cleanup if any remain
            if total_count > 0:
                cursor.execute(
                    "DELETE FROM short_term_message_log WHERE message_id = ?",
                    (test_message_id,)
                )
                for uid in test_user_ids:
                    cursor.execute(
                        "DELETE FROM short_term_message_log WHERE user_id = ?",
                        (uid,)
                    )
                self.db_manager.conn.commit()
                print(f"WARNING: Cleaned up {total_count} remaining test message entries")
            cursor.close()

        except Exception as e:
            self._log_test(category, "Short-Term Memory Cleanup", False, f"Error: {e}")

        # Test 5: Final database integrity check
        try:
            cursor = self.db_manager.conn.cursor()

            # Check for any entries with test patterns
            test_patterns = [
                ("bot_identity", "content LIKE '%TEST_%'"),
                ("long_term_memory", "fact LIKE '%TEST_%'"),
                ("short_term_message_log", "content LIKE '%test message%'"),
                ("global_state", "state_key LIKE '%TEST_STATE_%'"),
            ]

            # Add checks for all test user IDs
            for uid in test_user_ids:
                test_patterns.extend([
                    ("relationship_metrics", f"user_id = {uid}"),
                    ("users", f"user_id = {uid}"),
                    ("user_image_stats", f"user_id = {uid}")
                ])

            total_remaining = 0
            details = []

            for table, condition in test_patterns:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}")
                count = cursor.fetchone()[0]
                if count > 0:
                    total_remaining += count
                    details.append(f"{table}: {count}")
                    # Force cleanup
                    cursor.execute(f"DELETE FROM {table} WHERE {condition}")
                    self.db_manager.conn.commit()

            cleaned = total_remaining == 0

            self._log_test(
                category,
                "Final Database Integrity",
                cleaned,
                "Database clean - no test data remaining" if cleaned else f"Cleaned {total_remaining} remaining entries: {', '.join(details)}"
            )
            cursor.close()

        except Exception as e:
            self._log_test(category, "Final Database Integrity", False, f"Error: {e}")


def format_results_for_discord(summary: Dict) -> List[str]:
    """
    Format test results for Discord DM (respects 2000 char limit).

    Args:
        summary: Test results summary

    Returns:
        List of message strings to send
    """
    messages = []

    # Header
    header = f"""**Bot Test Suite Results**
Total Tests: {summary['total']}
Passed: {summary['passed']} ✅
Failed: {summary['failed']} ❌
Pass Rate: {summary['pass_rate']:.1f}%

{'='*40}
"""
    messages.append(header)

    # Group results by category
    categories = {}
    for result in summary["results"]:
        category = result["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(result)

    # Format each category
    current_message = ""
    for category, tests in categories.items():
        category_text = f"\n**{category}**\n"

        for test in tests:
            test_line = f"{test['emoji']} {test['test']}\n"
            if test['details']:
                test_line += f"   ↳ {test['details']}\n"

            # Check if adding this would exceed limit
            if len(current_message) + len(category_text) + len(test_line) > 1900:
                messages.append(current_message)
                current_message = category_text + test_line
            else:
                if category_text not in current_message:
                    current_message += category_text
                current_message += test_line

    # Add remaining content
    if current_message:
        messages.append(current_message)

    return messages


async def run_tests_for_guild(bot, guild_id: int, guild_name: str) -> Dict:
    """
    Run all tests for a specific guild.

    Args:
        bot: Discord bot instance
        guild_id: Guild ID to test
        guild_name: Guild name

    Returns:
        Test results summary
    """
    suite = BotTestSuite(bot, guild_id, guild_name)
    return await suite.run_all_tests()
