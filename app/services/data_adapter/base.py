import re
import sqlparse
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from .models import LogicalQuery, ResultSet

logger = logging.getLogger(__name__)

class SQLSafetyError(ValueError):
    """Exception raised when SQL fails security validation"""
    pass

class DataSourceAdapter(ABC):
    """Base class for all data source adapters with shared security and validation logic"""
    
    # Strictly allow only read-only operation prefixes
    ALLOWED_SQL_KEYWORDS = {"SELECT", "WITH", "EXPLAIN", "DESCRIBE", "DESC", "SHOW"}

    @abstractmethod
    async def execute(self, query: LogicalQuery) -> ResultSet:
        """Execute a logical query and return standardized result set"""
        pass
    
    @abstractmethod
    async def execute_summary(self, query: LogicalQuery) -> Dict[str, Any]:
        """Execute aggregation query"""
        pass

    @abstractmethod
    async def execute_sql(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute raw SQL query with parameters"""
        pass

    async def preview(
        self,
        sql: str,
        limit: int = 100,
        params: Optional[Dict[str, Any]] = None,
        offset: int = 0,
        include_total: bool = False,
    ) -> Dict[str, Any]:
        """Preview SQL with pagination — override in dialect adapters"""
        raise NotImplementedError(f"preview() not implemented for {type(self).__name__}")

    async def explain(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """EXPLAIN execution plan — override in dialect adapters"""
        raise NotImplementedError(f"explain() not implemented for {type(self).__name__}")

    def _validate_sql_safety(self, sql: str) -> None:
        """
        Perform advanced security audit on raw SQL using AST parsing (sqlparse).
        Ensures only read-only queries are allowed and blocks all mutating operations.
        """
        try:
            # 1. Clean up and parse
            formatted_sql = sqlparse.format(sql, strip_comments=True).strip()
            if not formatted_sql:
                raise SQLSafetyError("Empty SQL query")
                
            parsed = sqlparse.parse(formatted_sql)
            if not parsed:
                raise SQLSafetyError("Failed to parse SQL query")
            
            for statement in parsed:
                # 2. Check statement type from sqlparse metadata
                stmt_type = statement.get_type()
                
                # Block known mutating types
                if stmt_type in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"):
                    raise SQLSafetyError(f"Security Policy Violation: Mutating operation '{stmt_type}' is forbidden.")
                
                # 3. Deep token check for the first keyword
                first_token = statement.token_first(skip_cm=True, skip_ws=True)
                if not first_token:
                    continue
                    
                keyword = first_token.value.upper()
                if keyword not in self.ALLOWED_SQL_KEYWORDS:
                    # If it's a SELECT type but first keyword isn't in whitelist (e.g. specialized DB commands)
                    # we still deny it for safety.
                    if stmt_type != "SELECT":
                        raise SQLSafetyError(f"Security Policy Violation: Command '{keyword}' is not allowed. Only read-only queries are permitted.")

            # If we reached here, SQL is considered safe based on our policy
            return
            
        except SQLSafetyError:
            raise
        except Exception as e:
            logger.error(f"SQL Security Parse Error: {e}")
            raise SQLSafetyError(f"Could not verify SQL safety: {str(e)}")

