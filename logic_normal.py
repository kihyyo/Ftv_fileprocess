# -*- coding: utf-8 -*-
#########################################################
# python
import os
import sys
import datetime
import traceback
import threading
import re
import subprocess
import shutil
import json
import ast
import time
from framework import py_urllib
import rclone
#import platform
#import daum_tv

# third-party
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_
from guessit import guessit

# sjva 공용
from framework import app, db, scheduler, path_app_root, celery, py_unicode
from framework.job import Job
from framework.util import Util
from system.model import ModelSetting as SystemModelSetting
from framework.logger import get_logger

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelItem
import subprocess
from metadata.logic_ftv import LogicFtv
from lib_metadata.site_tmdb import SiteTmdbFtv
from lib_metadata.site_watcha import SiteWatchaTv

#########################################################

class LogicNormal(object):
    
    @staticmethod
    @celery.task
    def scheduler_function():
        try:
            logger.debug("해외TV 파일 처리 시작!")
            source_base_path = ModelSetting.get('source_base_path')
            sub_o_path = ModelSetting.get('sub_o_path')
            uhd_base_path = ModelSetting.get('uhd_base_path')
            error_path = ModelSetting.get('error_path')
            source_base_path = [ x.strip() for x in source_base_path.split(',') ]
            if not source_base_path:
                return None
                logger.debug("경로를 확인하세요")
            if None == '':
                return None
            try:
                for source_path in source_base_path:
                    if ModelSetting.get_bool('use_smi_to_srt'):
                        try:
                            import smi2srt
                            # if app.config['config']['use_celery']:
                            #     result = smi2srt.Logic.start_by_path.apply_async((source_path,))
                            #     result.get()
                            # else:
                            logger.debug("smi2srt 진행중")
                            smi2srt.Logic.start_by_path(work_path=source_path)
                            logger.debug("파일처리 시작")
                            LogicNormal.check_move_list(source_path, sub_o_path, error_path)
                        except Exception as exception: 
                            logger.error('Exception:%s', exception)
                            logger.error(traceback.format_exc()) 
                    else:
                        LogicNormal.check_move_list(source_path, sub_o_path, error_path)        
                    if ModelSetting.get_bool('emptyFolderDelete'):
                        LogicNormal.empty_folder_remove(source_path)
                    else:
                        logger.debug('해외 TV 파일처리 종료')                                         
            except Exception as e:
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            
    @staticmethod
    def load_videos(source_path):
        extradelete = ModelSetting.get('extradelete')
        extdelete = ModelSetting.get('extdelete')
        file_list = []
        delete_lists = [ x.strip().lower() for x in extradelete.split(',') ]
        delete_ext = [x.strip().lower() for x in extdelete.split(',')]
        for (path, dir, files) in os.walk(source_path.strip(), topdown=False):
            for filename in files:
                video_exts = ['.mp4', '.mkv', '.avi', '.wmv', '.flv']
                if os.path.isdir(source_path): pass
                if os.path.splitext(filename)[1] in video_exts:
                    file_list.append(os.path.join(path, filename))  
                elif filename.lower() in delete_lists:
                    try:
                        os.remove(os.path.join(path,filename))                              
                    except:
                        logger.debug('efr - FAILED:%s', os.path.join(path,filename))
                        pass
                elif os.path.splitext(filename)[1].lower() in delete_ext:
                    try:
                        os.remove(os.path.join(path,filename))
                    except:
                        logger.debug('efr - FAILED:%s', os.path.join(path,deletefile))
                        pass
            pass
        return file_list
                
                       
    @staticmethod
    def item_list(path, f):
        try:
            item = {}
            item['path'] = path
            item['name'] = os.path.basename(f)
            item['fullPath'] = f
            try:
                item['year'] = guessit(item['fullPath'])['year']
            except:
                item['year'] = None
            item['folder_title'] = guessit(item['fullPath'])['title']
            temp = re.sub('시즌', 's', item['name'])
            item['guessit'] = guessit(temp) 
            item['ext'] = os.path.splitext(f)[1].lower()      
            item['search_name'] = None
            item['uhd'] = 0
            return item
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def search(item):
        try:
            en_title = item['guessit']['title']
            year = item['year']
            logger.debug('파일이름: %s', item['name'])
            logger.debug('검색어: %s', en_title)
            
            if LogicFtv.search((), en_title, year) == []:
                if LogicNormal.isHangul(en_title) > 0 :
                    logger.debug('검색 실패, 추가 검색 중')
                    kor_title = re.sub('[^가-힣]', ' ', en_title).strip()
                    if LogicFtv.search((), kor_title, year) != []:
                        logger.debug('검색성공. 검색어: %s', kor_title)
                        en_title = kor_title
                    elif LogicFtv.search((), kor_title, year) == []:
                        ori_title = re.sub('[ㄱ-ㅎ가-힣]', '', en_title).strip()
                        if LogicFtv.search((), en_title, year) != []:
                            logger.debug('검색성공. 검색어: %s', en_title)
                            en_title = ori_title
                if LogicFtv.search((), en_title, year) == []:
                    logger.debug('검색 실패. 폴더까지 확대 탐색')
                    en_title = item['folder_title']
                    if LogicFtv.search((), en_title, year) != []:
                        logger.debug('검색성공. 검색어: %s', en_title)
                    if LogicFtv.search((), en_title, year) == []: 
                        if LogicNormal.isHangul(en_title) > 0 :
                            kor_title = re.sub('[^가-힣]', ' ', en_title).strip()
                            if LogicFtv.search((), kor_title, year) != []:
                                logger.debug('검색성공. 검색어: %s', kor_title)
                                en_title = kor_title
                            elif LogicFtv.search((), kor_title, year) == []:
                                ori_title = re.sub('[ㄱ-ㅎ가-힣]', '', en_title).strip()
                                if LogicFtv.search((), ori_title, year) != []:
                                    logger.debug('검색성공. 검색어: %s', ori_title)
                                    en_title = ori_title
                                else:                                
                                    tmdb = None
                                    logger.debug('검색 실패')
                        else:
                            tmdb = None
                            logger.debug('검색 실패')
                                     
            if LogicFtv.search((), en_title, year) != []:
                if year is not None:
                    logger.debug('연도: %s', year)
                    tmdb_code = LogicFtv.search((), en_title)[0]['code'].strip()
                    i = 0 
                    while 0<= i < len(LogicFtv.search((), en_title, year)):       
                        if abs(int(LogicFtv.search((), en_title, year)[i]['year']) - year) < 2:
                            logger.debug('TMDB year = %s', LogicFtv.search((), en_title, year)[i]['year'])         
                            tmdb_code = LogicFtv.search((), en_title, year)[i]['code'].strip()
                            break
                        else:
                            i = i + 1
                    tmdb = SiteTmdbFtv.info(tmdb_code)
                else:
                    tmdb_code = LogicFtv.search((), en_title)[0]['code'].strip()
                tmdb = SiteTmdbFtv.info(tmdb_code)
                watcha = SiteWatchaTv.search(tmdb['data']['title'], tmdb['data']['year'])
                if not LogicNormal.isHangul(tmdb['data']['title']) > 0 :
                    logger.debug('TMDB 한글제목 아님. 추가 검색')
                    try:                          
                        if watcha['ret'] == 'empty':
                            logger.debug('검색 실패')
                            pass
                        else:
                            i = 0
                            while 0<= i <= len(watcha['data']) - 1:
                                try:
                                    t_watcha = watcha['data'][i]['title_en'].strip()
                                except:
                                    t_watcha = 'no_title_en' 
                                t_tmdb = tmdb['data']['title'].strip()      
                                if t_watcha == t_tmdb and abs(int(watcha['data'][i]['year']) - int(tmdb['data']['year'])) < 2 and LogicNormal.isHangul(watcha['data'][i]['title']) > 0 :                                                  
                                    logger.debug('한글 제목 매칭 성공')
                                    tmdb['data']['title'] = watcha['data'][i]['title']
                                    break                                                                                       
                                else:
                                    i = i + 1                                              
                    except Exception as e:
                        logger.error('Exception:%s', e)
                        logger.error(traceback.format_exc())              
                logger.debug('폴더명: %s', tmdb["data"]["title"])
                if tmdb['data']['country'] == []:
                    logger.debug('TMDB 국가 정보 없음')
                    if watcha['ret'] == 'empty':  
                        tmdb['data']['country'] == None
                    if watcha['ret'] == 'success':
                        i = 0
                        while 0<= i < len(watcha['data']):
                            if watcha['data'][i]['title'] == tmdb['data']['title'] and abs(int(watcha['data'][i]['year']) - int(tmdb['data']['year'])) < 2:       
                                if not watcha['data'][i]['country'] == []:
                                    logger.debug('왓챠 국가정보 있음')           
                                    tmdb['data']['country'] == watcha['data'][i]['country']
                                else:
                                    try:
                                        logger.debug('왓챠 메인 국가 정보 없음, 시리즈에서 국가 정보 검색') 
                                        tmdb['data']['country'].insert(0, watcha['data'][i]['seasons'][0]['info']['country'][0]) 
                                        logger.debug('국가정보: %s', tmdb['data']['country'][0])
                                    except:
                                        pass
                                break                                 
                            else:
                                i = i + 1                                                      
                return tmdb
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            
    @staticmethod
    def set_ftv(data, ftv):
        interval = ModelSetting.get('interval')
        data['ftv'] = ftv
        tmp = ""
        try:                                  
            if ftv is not None:
                data['dest_folder_name'] = '%s' % (re.sub('[\\/:*?"<>|]', '', ftv['data']['title']).replace('  ', ' '))                
                folder_rule = ModelSetting.get_setting_value('folder_rule')
                tmp = folder_rule.replace('%TITLE%', ftv['data']['title']).replace('%YEAR%', str(ftv['data']['year'])).replace('%ORIGINALTITLE%', ftv['data']['originaltitle'])
                tmp = re.sub('[\\/:*?\"<>|]', '', tmp).replace('  ', ' ').replace('[]', '')
                data['dest_folder_name'] = tmp 
                time.sleep(int(interval))  
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def check_kor_sub(data, tmdb, sub_o_path):
        logger.debug('자막 체크 시작!')
        try:
            if data['guessit']['release_group'] in ['SW', 'ST', 'SAP']:
                logger.debug('VOD 파일')
                return True
            if os.path.isfile(os.path.splitext(data['fullPath'])[0]+'.ko.srt'):
                logger.debug('외부 자막 있음') 
                LogicNormal.file_move(os.path.splitext(data['fullPath'])[0]+'.ko.srt',data['dest'],os.path.splitext(data['name'])[0]+'.ko.srt')
                return True  
            if os.path.isfile(os.path.splitext(data['fullPath'])[0]+'.smi'):
                logger.debug('외부 자막 있음') 
                LogicNormal.file_move(os.path.splitext(data['fullPath'])[0]+'.smi',data['dest'],os.path.splitext(data['name'])[0]+'.smi')
                return True 
            if os.path.isfile(os.path.splitext(data['fullPath'])[0]+'.srt'):
                logger.debug('외부 자막 있음') 
                LogicNormal.file_move(os.path.splitext(data['fullPath'])[0]+'.srt',data['dest'],os.path.splitext(data['name'])[0]+'.srt')
                return True                
            else:
                logger.debug('외부 자막 없음') 
                try:
                    command = ['ffprobe', '-loglevel', 'error', '-select_streams', 's', '-show_entries', 'stream_tags=language', '-of', 'csv=p=0', data['fullPath']]
                    output = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, encoding='utf-8')
                    ffprobe_json = json.dumps(output.communicate())
                    if 'kor' in ffprobe_json:
                        logger.debug('내장 한글 자막 있음')
                        return True
                    else:
                        logger.debug('한글 자막 없음')
                        return False
                except Exception as e:
                    logger.error('Exception:%s', e)
                    logger.error(traceback.format_exc())
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def file_move(fullPath, dest, f):
        try:
            if os.path.exists(dest):
                if os.path.exists(os.path.join(dest, f)):
                    logger.debug('타겟 파일: %s', os.path.exists(os.path.join(dest, f)))
                    logger.debug('같은 파일 있음')
                    if os.path.getsize(fullPath) == os.path.getsize(os.path.join(dest,f)):
                        logger.debug('대상 %s 사이즈가 같아 그냥 삭제', f)
                        os.remove(fullPath)
                    else:
                        os.path.getsize(fullPath) != os.path.getsize(os.path.join(dest,f))
                        logger.debug('대상 %s 사이즈가 달라 기존 파일 삭제', f)
                        os.remove(os.path.join(dest,f))                    
                        shutil.move(fullPath,os.path.join(dest,f))
                if not os.path.isfile(os.path.join(dest,f)):                       
                    shutil.move(fullPath, os.path.join(dest, f))          
            if not os.path.exists(dest): 
                os.makedirs(dest)
                if not os.path.isfile(os.path.join(dest,f)):                       
                    shutil.move(fullPath, os.path.join(dest, f))      
        except Exception as exception:
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())

    @staticmethod
    def genre_move(data, tmdb, sub_o_path):
        ani_base_path = ModelSetting.get('ani_base_path')
        genre_base_path = ModelSetting.get('genre_base_path')
        error_path = ModelSetting.get('error_path')
        try:
            if str(data['guessit']['season']) == str(0):
                season = 'Specials'
            else:
                season = 'Season '+str(data['guessit']['season'])
        except:
            season = 'Season '+str(1)
        try:
            release_group = data['guessit']['release_group']
        except:
            data['guessit']['release_group'] = 'no_release'
            release_group = 'no_release'      
        if tmdb is not None:           
            try:
                if '애니메이션' in tmdb['data']['genre']:
                    if ModelSetting.get_bool('ani_flag'):
                        logger.debug('애니메이션 파일')
                    try:
                        data['dest']=os.path.join(ani_base_path,data['dest_folder_name'],season)
                        if LogicNormal.check_kor_sub(data, tmdb, sub_o_path):  
                            logger.debug('이동경로:%s', data['dest'])
                            LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                            LogicNormal.db_save(data, data['dest'], 'sub_o', True)  
                        else:
                            if ModelSetting.get_bool('sub_x_flag'):
                                data['dest']=os.path.join(error_path,'sub_x',data['dest_folder_name'],season,release_group)
                                LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                                LogicNormal.db_save(data, data['dest'], 'sub_x', True)
                            else:
                                data['dest']=os.path.join(error_path,'sub_x',data['dest_folder_name'],season)
                                LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                                LogicNormal.db_save(data, data['dest'], 'sub_x', True)
                    except Exception as e:
                        logger.error('Exxception:%s', e)
                        logger.error(traceback.format_exc())
                elif u'리얼리티' in tmdb['data']['genre'] or u'다큐멘터리' in tmdb['data']['genre']:
                    if ModelSetting.get_bool('genre_flag'):
                        logger.debug('장르: 다큐멘터리')
                        try:
                            data['dest']=os.path.join(genre_base_path,data['dest_folder_name'],season)
                            if LogicNormal.check_kor_sub(data, tmdb, sub_o_path):
                                logger.debug('이동경로:%s', data['dest'])
                                LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                                LogicNormal.db_save(data, data['dest'], 'sub_o', True) 
                            else:
                                if ModelSetting.get_bool('sub_x_flag'):
                                    data['dest']=os.path.join(error_path,'sub_x',data['dest_folder_name'],season,release_group)
                                    LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                                    LogicNormal.db_save(data, data['dest'], 'sub_x', True)
                                else:
                                    data['dest']=os.path.join(error_path,'sub_x',data['dest_folder_name'],season)
                                    LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                                    LogicNormal.db_save(data, data['dest'], 'sub_x', True)
                        except Exception as e:
                            logger.error('Exxception:%s', e)
                            logger.error(traceback.format_exc())
                else:
                    LogicNormal.move_ftv(data, tmdb, sub_o_path)
            except Exception as e:
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
        if tmdb is None:
            if ModelSetting.get_bool('sub_x_flag'):
                data['dest']=os.path.join(error_path,'no_meta',data['guessit']['title'],season,release_group)
                LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                LogicNormal.db_save(data, data['dest'], '불일치', True)
            else:
                data['dest']=os.path.join(error_path,'no_meta',data['guessit']['title'],season)
                LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                LogicNormal.db_save(data, data['dest'], '불일치', True)
            
                           
    @staticmethod
    def move_ftv(data, tmdb, sub_o_path):
        try:
            sub_o_path = ModelSetting.get('sub_o_path')
            uhd_base_path = ModelSetting.get('uhd_base_path')      
            error_path = ModelSetting.get('error_path')
            try:
                if str(data['guessit']['season']) == str(0):
                     season = 'Specials'
                else:
                    season = 'Season '+str(data['guessit']['season'])
            except:
                season = 'Season '+str(1)
            try:
                release_group = data['guessit']['release_group']
            except:
                release_group = 'no_release'
           
            command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=height', '-of', 'csv=s=x:p=0', data['fullPath']]
            output = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, encoding='utf-8')
            ffprobe_json = json.dumps(output.communicate())
            if (ModelSetting.get_bool('uhd_flag') and '1920' in ffprobe_json) or (ModelSetting.get_bool('uhd_flag') and '2160' in ffprobe_json):
                try: 
                    logger.debug('UHD 파일')
                    try:
                        cu_user_list = ast.literal_eval(ModelSetting.get_setting_value('uhd_country_option').strip())
                        c = tmdb['data']['country'][0]
                        if c in cu_user_list.keys():
                            cu = cu_user_list[c]
                        else:
                            cu = ModelSetting.get_setting_value('etc_uhd_country').strip()
                    except:
                        cu = ModelSetting.get_setting_value('etc_uhd_country').strip()                         
                        data['dest']=os.path.join(uhd_base_path,cu,data['dest_folder_name'],season)
                        if LogicNormal.check_kor_sub(data, tmdb, sub_o_path):
                            logger.debug('이동경로:%s', data['dest'])
                            LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                            LogicNormal.db_save(data, data['dest'], 'sub_o', True)
                        else:
                            if ModelSetting.get_bool('sub_x_flag'):
                                data['dest']=os.path.join(error_path,'sub_x',data['dest_folder_name'],season,release_group)
                                LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                                LogicNormal.db_save(data, data['dest'], 'sub_x', True)
                            else: 
                                data['dest']=os.path.join(error_path,'sub_x',data['dest_folder_name'],season)
                                LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                                LogicNormal.db_save(data, data['dest'], 'sub_x', True)
                except:
                    pass
            else:
                try:
                    cg_user_list = ast.literal_eval(ModelSetting.get_setting_value('ftv_country_option').strip())
                    c = tmdb['data']['country'][0]
                    if c in cg_user_list.keys():
                        cg = cg_user_list[c]
                    else:
                        cg = ModelSetting.get_setting_value('etc_ftv_country').strip()
                except:
                    cg = ModelSetting.get_setting_value('etc_ftv_country').strip()    
                data['dest']=os.path.join(sub_o_path,cg,data['dest_folder_name'],season)
                if LogicNormal.check_kor_sub(data, tmdb, sub_o_path):
                    logger.debug('이동경로:%s', data['dest'])
                    LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                    LogicNormal.db_save(data, data['dest'], 'sub_o', True)
                else:
                    if ModelSetting.get_bool('sub_x_flag'):
                        data['dest']=os.path.join(error_path,'sub_x',data['dest_folder_name'],season,release_group)
                        LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                        LogicNormal.db_save(data, data['dest'], 'sub_x', True)
                    else:
                        data['dest']=os.path.join(error_path,'sub_x',data['dest_folder_name'],season)
                        LogicNormal.file_move(data['fullPath'],data['dest'],data['name'])
                        LogicNormal.db_save(data, data['dest'], 'sub_x', True)                                                                                        
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())      
            
    @staticmethod
    def empty_folder_remove(base_path):
        try:
            logger.debug('efr - base_path:%s', base_path)
            for root, dirs, files in os.walk(base_path, topdown=False):
                for name in dirs:
                    try:
                        if len(os.listdir(os.path.join(root, name))) == 0:
                            logger.debug('efr - Deleting:%s', os.path.join(root, name))
                            try:
                                os.rmdir(os.path.join(root, name))
                            except:
                                logger.debug('efr - FAILED:%s', os.path.join(root, name))
                                pass
                    except:
                        pass
            logger.debug('해외 TV 파일처리 종료')
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def check_move_list(source_path, sub_o_path, error_path):
        source_path = LogicNormal.load_videos(source_path)
        for f in source_path:
            path = os.path.dirname(f)
            item = LogicNormal.item_list(path, f)
            tmdb = LogicNormal.search(item)
            LogicNormal.set_ftv(item, tmdb)
            LogicNormal.genre_move(item, tmdb, sub_o_path)
         
    @staticmethod
    def db_save(data, dest, match_type, is_moved):
        # telegram_flag = ModelSetting.get_bool('telegram')
        try:
            entity = {}
            entity['name'] = data['guessit']['title']
            entity['fileName'] = data['name']
            entity['dirName'] = os.path.basename(data['fullPath'])
            entity['targetPath'] = dest
            entity['match_type'] = match_type
            if is_moved:
                entity['is_moved'] = 1
            else:
                entity['is_moved'] = 0
            ModelItem.save_as_dict(entity)
            # if telegram_flag == 1:
            #     text = u'파일정리\n [%s] %s -> %s\n' % (match_type, data['fullPath'], dest)
            #     #import framework.common.notify as Notify
            #     #Notify.send_message(text, message_id = 'files_move_result')
            #     from tool_base import ToolBaseNotify
            #     ToolBaseNotify.send_message(text, message_id = 'files_move_result')
        except Exception as e:
            logger.error('Exxception:%s', e)
            logger.error(traceback.format_exc())        
              
    @staticmethod
    def isHangul(text):
        #Check the Python Version
        pyVer3 =  sys.version_info >= (3, 0)

        if pyVer3 : # for Ver 3 or later
            encText = text
        else: # for Ver 2.x
            if type(text) is not unicode:
                encText = text.decode('utf-8')
            else:
                encText = text

        hanCount = len(re.findall(u'[\u3130-\u318F\uAC00-\uD7A3]+', encText))
        return hanCount > 0
             
    
    
