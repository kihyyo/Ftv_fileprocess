# -*- coding: utf-8 -*-
#########################################################
# python
import os
import sys
import traceback
import time
import threading
import subprocess
import requests

# third-party

# sjva 공용
from framework import db, scheduler, path_data, path_app_root, celery
from framework.job import Job
from framework.util import Util
from sqlalchemy import desc, or_, and_, func, not_

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelItem

from .logic_normal import LogicNormal
#########################################################


class Logic(object):
    # 디폴트 세팅값
    db_default = {
        'db_version' : '1',
		'source_base_path' : '',
		'sub_o_path' : '',
		'use_smi_to_srt' : '',
		'ftv_country_option' : u'{"미국":"미국드라마", "영국":"영국드라마", "중국":"중국드라마", "일본":"일본드라마"}',
		'etc_ftv_country' : u'기타국가드라마',
		'uhd_flag' : '',		
		'uhd_base_path' : '',
		'uhd_country_option' : u'{"미국":"미국드라마", "영국":"영국드라마", "중국":"중국드라마", "일본":"일본드라마"}',
		'etc_uhd_country' : u'기타국가드라마',	
		'ani_flag' : '',	
		'ani_base_path' : '',
		'genre_flag' : '',
		'genre_base_path' : '',
		'error_path' : '',
        		'sub_x_flag' : '',
        'folder_rule': '%TITLE% [%ORIGINALTITLE%] (%YEAR%)',        
        'schedulerInterval' : '60',
        'interval' : '1',
        'emptyFolderDelete' : 'False',
        'extradelete' : u'rarbg.txt, RARBG_DO_NOT_MIRROR.exe',
        'extdelete' : '.html',
        'extraMove' : 'False',     
        'emptyFolderDelete' : 'False',
        'auto_start' : 'False',
        'telegram' : ''
    }

    session = None

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_load():
        try:
            logger.debug('%s plugin_load', package_name)
            Logic.db_init()

            if ModelSetting.get_bool('auto_start'):
                Logic.scheduler_start()
            # 편의를 위해 json 파일 생성
            from .plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_start():
        try:
            logger.debug('%s scheduler_start' % package_name)
            #interval = ModelSetting.query.filter_by(key='schedulerInterval').first().value
            interval = ModelSetting.get('schedulerInterval')
            job = Job(package_name, package_name, interval, Logic.scheduler_function, u"파일정리", False)
            scheduler.add_job_instance(job)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_stop():
        try:
            logger.debug('%s scheduler_stop' % package_name)
            scheduler.remove_job(package_name)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def scheduler_function():
        try:
            #Test
            ##LogicNormal.scheduler_function()
            from framework import app
            if app.config['config']['use_celery']:
                result = LogicNormal.scheduler_function.apply_async()
                result.get()
            else:
                LogicNormal.scheduler_function()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def reset_db():
        try:
            db.session.query(ModelItem).delete()
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def one_execute():
        try:
            if scheduler.is_include(package_name):
                if scheduler.is_running(package_name):
                    ret = 'is_running'
                else:
                    scheduler.execute_job(package_name)
                    ret = 'scheduler'
            else:
                def func():
                    time.sleep(2)
                    Logic.scheduler_function()
                threading.Thread(target=func, args=()).start()
                ret = 'thread'

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'
        return ret
