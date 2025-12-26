import os
import time

def get_setting(key, default=None):
    """설정 조회 (DB 전용)"""
    try:
        from database_helpers import get_setting as db_get_setting
        return db_get_setting(key, default)
    except Exception as e:
        return default

def set_setting(key, value):
    """설정 저장 (DB 전용)"""
    try:
        from database_helpers import save_setting as db_save_setting
        return db_save_setting(key, value)
    except Exception as e:
        return False

def cached_setting(key, default=''):
    """캐시된 설정 조회"""
    return get_setting(key, default)