#!/usr/bin/env python3
"""
Validate that secrets are properly configured before deployment.

This script performs pre-deployment checks to ensure:
1. No secrets are committed to git
2. Required environment variables are set
3. Secrets meet minimum security requirements

Usage:
    python backend/scripts/validate_secrets.py
    python backend/scripts/validate_secrets.py --strict  (fail on warnings)

Exit codes:
    0 = All checks passed
    1 = Critical check failed (must fix before deploy)
    2 = Warning-level issue (should fix, but not blocking)
"""

import os
import sys
import subprocess
from pathlib import Path


class ValidationError(Exception):
    """Critical validation failure."""
    pass


class ValidationWarning(Exception):
    """Non-critical validation warning."""
    pass


def check_no_secrets_in_git() -> None:
    """Verify sensitive env files are not tracked by git."""
    print("Checking git-tracked env files...")

    repo_root = Path(__file__).resolve().parents[2]

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "--", ".env", "backend/.env"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.stdout.strip():
            raise ValidationWarning(
                "⚠️  WARNING: .env file is tracked in git. "
                "Add '.env' to .gitignore to prevent accidentally committing secrets."
            )
    except Exception as e:
        if isinstance(e, ValidationWarning):
            raise
        print(f"  Skipping git check (git may not be available): {e}")


def check_environment_variables() -> None:
    """Verify required environment variables are set."""
    print("Checking environment variables...")
    
    app_env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    
    if app_env not in {"production", "prod"}:
        print(f"  Non-production environment detected ({app_env}). Skipping strict checks.")
        return
    
    print(f"  Production environment detected ({app_env}). Checking secrets...")
    
    # Required in production
    required_secrets = ["SECRET_KEY"]
    
    for secret in required_secrets:
        value = os.getenv(secret)
        if not value:
            raise ValidationError(f"✗ CRITICAL: {secret} is not set in production")
        
        if len(value) < 32:
            raise ValidationError(
                f"✗ CRITICAL: {secret} is too short ({len(value)} bytes). "
                "Minimum 32 bytes required."
            )
        
        # Check for weak patterns
        weak_patterns = [
            "change-me",
            "test",
            "debug",
            "default",
            "insecure",
        ]
        
        if any(p in value.lower() for p in weak_patterns):
            raise ValidationError(
                f"✗ CRITICAL: {secret} contains weak pattern. "
                "Generate a strong random value with: "
                "python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        print(f"  ✓ {secret} is set and meets minimum requirements")


def check_file_permissions() -> None:
    """Verify secret files have restricted permissions."""
    print("Checking file permissions...")
    
    # Check if .env file exists locally
    env_file = Path(".env")
    if env_file.exists():
        mode = os.stat(env_file).st_mode
        # Should be readable only by owner (600 = -rw-------)
        if mode & 0o077:  # Check if group or others have any permissions
            raise ValidationWarning(
                f"⚠️  WARNING: .env file has overly permissive permissions (mode: {oct(mode)}). "
                "Should be 600 (readable only by owner). Fix with: chmod 600 .env"
            )
        else:
            print("  ✓ .env file has correct permissions (600)")


def check_environment_specific_issues() -> None:
    """Check for environment-specific configuration issues."""
    print("Checking environment-specific configuration...")
    
    app_env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    
    if app_env in {"production", "prod"}:
        # In production, ensure HTTPS is being used
        auth_cookie_secure = os.getenv("AUTH_COOKIE_SECURE", "1")
        if auth_cookie_secure != "1":
            raise ValidationWarning(
                "⚠️  WARNING: AUTH_COOKIE_SECURE is not set to '1' in production. "
                "Cookies will not have the Secure flag, making them vulnerable to MITM attacks. "
                "Set: AUTH_COOKIE_SECURE=1"
            )
        else:
            print("  ✓ AUTH_COOKIE_SECURE is properly set")
        
        # Check for CSP header configuration
        csp = os.getenv("CONTENT_SECURITY_POLICY")
        if not csp:
            print("  ℹ️  Using default Content-Security-Policy header")
        else:
            print("  ✓ Custom Content-Security-Policy is configured")
    
    print(f"  ✓ Environment '{app_env}' configuration validated")


def main():
    """Run all validation checks."""
    strict_mode = "--strict" in sys.argv
    
    print("=" * 60)
    print("Secrets Validation Check (Issue #415)")
    print("=" * 60)
    
    checks = [
        ("Git History", check_no_secrets_in_git),
        ("Environment Variables", check_environment_variables),
        ("File Permissions", check_file_permissions),
        ("Environment Configuration", check_environment_specific_issues),
    ]
    
    failed = False
    warnings = False
    
    for check_name, check_func in checks:
        try:
            print(f"\n[{check_name}]")
            check_func()
        except ValidationError as e:
            print(f"  {e}")
            failed = True
        except ValidationWarning as e:
            print(f"  {e}")
            warnings = True
        except Exception as e:
            print(f"  ⚠️  Unexpected error: {e}")
            if strict_mode:
                failed = True
    
    print("\n" + "=" * 60)
    
    if failed:
        print("❌ VALIDATION FAILED (Critical issues found)")
        print("=" * 60)
        return 1
    elif warnings and strict_mode:
        print("⚠️  VALIDATION PASSED WITH WARNINGS (Strict mode enabled)")
        print("=" * 60)
        return 2
    elif warnings:
        print("✓ VALIDATION PASSED (Warnings present)")
        print("=" * 60)
        return 0
    else:
        print("✓ VALIDATION PASSED (All checks successful)")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
