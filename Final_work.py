import os
from pprint import pprint
import requests
import time
from tqdm import tqdm
import pandas as pd
import json
import settings
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
gauth = GoogleAuth()
gauth.LocalWebserverAuth()

class VKUser:
    url = 'https://api.vk.com/method/'
    def __init__(self, TOKEN_VK, version):
        self.params = {'access_token': TOKEN_VK,
                       'v': version
                       }

    def _get_user_id(self, user_name):
        """Служебная функция, получающая id пользователя в ВК по его короткому имени"""
        url_user_id = self.url + 'users.get'
        params_id = {'user_ids': user_name,
                     }
        response = requests.get(url_user_id, params={**self.params, **params_id}).json()
        return response['response'][0]['id']


    def _get_photos_info(self, user_name):
        """Служебная функция, получающая информацию о фотографиях с аватарок пользователя в ВК"""
        id_user = self._get_user_id(user_name)
        url_photos = self.url + 'photos.get'
        params_photos = {'owner_id': id_user,
                         'album_id': 'profile',
                         'rev': 0,
                         'extended': 1,
                         'photo_sizes': 0,
                         'count': 10
                         }
        response = requests.get(url_photos, params={**self.params, **params_photos}).json()
        all_photo = response['response']['items']
        all_photos_info = []
        for photo in all_photo:
            photo_info = {'file_name': f"{photo['likes']['count']}",
                          'sizes': [photo['sizes'][-1]['type'], photo['sizes'][-1]['url'], photo['date']]}
            all_photos_info.append(photo_info)
        return all_photos_info

    def get_json_file(self, user_name, file_name):
        """Метод, создающий в директории файл в формате JSON c информацией о фото, использующихся в качестве
        аватарок. В качестве параметоров передается короткое имя пользователя и имя создаваемого файла"""
        id_user = self._get_user_id(user_name)
        url_photos = self.url + 'photos.get'
        params_photos = {'owner_id': id_user,
                         'album_id': 'profile',
                         'rev': 0,
                         'extended': 1,
                         'photo_sizes': 0,
                         'count': 10
                         }
        response = requests.get(url_photos, params={**self.params, **params_photos}).json()
        all_photo = response['response']['items']
        all_photos_info = []
        for photo in all_photo:
            photo_info = {'file_name': f"{photo['likes']['count']}.jpg",
                          'sizes': photo['sizes'][-1]['type']}
            all_photos_info.append(photo_info)
        with open(f"{file_name}.json", 'w') as f:
            json.dump(all_photos_info, f, indent=2)
        return f"File with name '{file_name}.json' was create on you directory"


    def _get_headers_yandex(self):
        """Служебная функция, передающая заголовки в другие функции для отправки запросов на Яндекс-Полигон"""
        return {'Content_type': 'applications/json',
                'Authorization': settings.YANDEX_TOKEN}


    def _create_dir(self, dir_name):
        """Служебная функция, создающая папку с именем 'dir_name', которое передается в параметрах,
        на Яндекс диске. Функция возвращает имя созданной папки"""
        url_dir = 'https://cloud-api.yandex.net/v1/disk/resources'
        if requests.get(url_dir, headers=self._get_headers_yandex(),
                        params={'path': '/{}'.format(dir_name)}).status_code == 404:
            headers = self._get_headers_yandex()
            params = {'path': '/{}'.format(dir_name),
                      'fields': 'href,method,templated'}
            response = requests.put(url_dir, headers=headers, params=params)
        return f"/{dir_name}"


    def download_to_yandex(self, user_id, dir_name):
        """Функция, загружающая фото с аватарок пользователя в ВК в директорию на Яндекс диске.
        В качестве параметров передаются id-пользователя, либо его короткое имя и имя Директории.
        В качестве имени фотографий выступает кол-во лайков на фотографии. В случае одинакового кол-ва лайков,
        к имени фотографии добавляется дата создания"""
        url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        headers = self._get_headers_yandex()
        photos = self._get_photos_info(user_id)
        name_dir = self._create_dir(dir_name)
        all_name_photo = []
        for photo in tqdm(photos):
            time.sleep(1)
            if f"{photo['file_name']}.jpg" not in all_name_photo:
                params = {'path': f"{name_dir}/{photo['file_name']}.jpg",
                          'url': photo['sizes'][1]}
                response = requests.post(url, headers=headers, params=params)
            else:
                params1 = {'path': f"{name_dir}/{photo['file_name']}_{str(photo['sizes'][2])}.jpg",
                           'url': photo['sizes'][1]}
                response1 = requests.post(url, headers=headers, params=params1)
            all_name_photo.append(f"{photo['file_name']}.jpg")


    def _get_followers_id(self, name):
        """Служебная функция, возвращающая список первой 1000 id-подписчиков(в формате 'str') пользователя в ВК.
        В качестве параметоров передается короткое имя пользователя либо его id"""
        user_id = self._get_user_id(name)
        url_followers_info = self.url + 'users.getFollowers'
        count = 100
        offset = 0
        all_followers_id = []
        while offset < 1000:
            params_followers = {'user_id': user_id,
                                'offset': offset,
                                'count': count,
                                'fields': 'about, activities'
                                }
            response = requests.get(url_followers_info, params={**self.params, **params_followers}).json()
            info_all = response['response']['items']
            all_id = []
            for info in info_all:
                id_f = str(info['id'])
                all_id.append(id_f)
            offset += 100
            time.sleep(0.5)
            all_followers_id.extend(all_id)
        return all_followers_id



    def get_followers_info(self, name_user, name_file):
        """Функция, создающая датафрейм с информацией о первых 100 подписчиках пользователя в ВК с наибольшим
        количеством подписчиков. Датафрейм создается в формате xlsx. В качестве параметоров передается id-пользователя
        либо его короткое имя и имя файла в формате - имя.xlsx"""
        url_user_info = self.url + 'users.get'
        params_info = {'user_ids': ','.join(self._get_followers_id(name_user)),
                       'fields': 'id,first_name,last_name,bdate,activities,followers_count,interests,'
                                 'military,religion,status,photo_400_orig',
                       'name_case': 'nom'}
        response = requests.get(url_user_info, params={**self.params, **params_info}).json()
        all_info = response['response']
        df = pd.DataFrame(all_info)
        df.drop(['can_access_closed', 'is_closed', 'status_audio'], axis=1, inplace=True)
        df.rename(columns={'first_name':'Имя', 'last_name':'Фамилия','bdate':'Дата рождения','photo_400_orig':'Фото',
                           'status':'Статус','interests':'Интересы','activities':'Последний вход',
                           'followers_count':'Кол-во подписчиков'}, inplace=True)
        df_sort = df.sort_values(by=['Кол-во подписчиков'], ascending=False)
        df_100 = df_sort.nlargest(100, 'Кол-во подписчиков')
        df_100.to_excel(name_file)
        return f"File with name '{name_file}' was create"


    def _id_all_albums(self, name_user):
        """Служебный метод, получайщий id в формате str всех альбомов пользователя"""
        url_id = self.url + 'photos.getAlbums'
        id_user = self._get_user_id(name_user)
        params_id = {'owner_id': id_user,
                     'photo_sizes': 1}
        response = requests.get(url_id, params={**self.params, **params_id}).json()['response']['items']
        all_id_albums = []
        for albums in response:
            id_album = str(albums['id'])
            all_id_albums.append(id_album)
        return all_id_albums

    def _info_photos_in_albums(self, name_user):
        """Служебный метод, вовзращающий информаию о всех фото из всех доступных альбомов пользователя.
        В качестве параметров передается короткое имя либо id"""
        url_albums = self.url + 'photos.get'
        id_user = self._get_user_id(name_user)
        all_id_albums = self._id_all_albums(id_user)
        all_photos_in_albums = []
        for id_album in all_id_albums:
            params_album = {'owner_id': id_user,
                            'album_id': id_album,
                            'extended': 1}
            response = requests.get(url_albums, params={**self.params, **params_album}).json()['response']['items']
            all_photos_in_albums.extend(response)
        return all_photos_in_albums

    def download_all_photos_in_yandex(self, name_user, dir_name):
        """Метод, загружающий фотографии максимальных размеров из всех альбомов пользователя.
         В качестве параметров передается имя пользователя или его id, а также имя директории для загрузки на
         Яндекс диск"""
        url = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
        headers = self._get_headers_yandex()
        id_user = self._get_user_id(name_user)
        all_photos = self._info_photos_in_albums(name_user)
        dir = self._create_dir(dir_name)
        all_name_photo = []
        for photo in tqdm(all_photos):
            time.sleep(0.5)
            if f"{photo['likes']['count']}.jpg" not in all_name_photo:
                params_photo = {'path': f"{dir}/{photo['likes']['count']}.jpg",
                                'url': photo['sizes'][-1]['url']}
                response = requests.post(url, headers=headers, params=params_photo)
            else:
                params_photo1 = {'path': f"{dir}/{photo['likes']}_{str(photo['date'])}",
                                 'url': photo['sizes'][-1]['url']}
                response1 = requests.post(url, headers=headers, params=params_photo1)
            all_name_photo.append(f"{photo['likes']['count']}.jpg")
        return f"All photos was downloads in directory with name '{dir_name}'"

vk_client = VKUser(settings.TOKEN_VK, 5.131)

                                    #### РАБОТА С ИНСТАГРАММ ######

class Inst:
    def user_info(self, version, user_id):
        """Метод, получающий общую информацию о странице пользователя Инстаграмм"""
        url = 'https://graph.instagram.com/' + f"{version}/" + f"{user_id}"
        params = {'fields': 'account_type,id,media_count,username',
                  'access_token': settings.MARKER_INST}
        response = requests.get(url, params=params).json()
        return response

    def _user_media_id(self):
        """Служебный метод, получающая все id фотографий из инстаграмм пользователя"""
        url = 'https://graph.instagram.com/me/media'
        params = {'fields': 'account_type,id,media_count,username',
                  'access_token': settings.MARKER_INST}
        response = requests.get(url, params=params).json()
        all_id_media = response['data']
        all_id = []
        for id_media in all_id_media:
            all_id.append(id_media['id'])
        return all_id

    def _all_media_info(self):
        """Служебный метод, получающая в качестве результата информацию о всех фото пользователя
        в инстаграмм в формате словаря, где ключом является id фотографии, значением URL на фото"""
        all_id_media = self._user_media_id()
        url = 'https://graph.instagram.com/'
        params = {'fields': 'id, media_url',
                  'access_token': settings.MARKER_INST}
        all_photos_url = {}
        for info in all_id_media:
            full_url = url + info
            response = requests.get(full_url, params=params).json()
            all_photos_url[response['id']] = response['media_url']
        return all_photos_url

    def download_all_photo_from_inst_to_dir(self, dir_name='Photo from Insta'):
        """Метод, загружающий все фото пользователя инстаграмм в отдельную директорию на компбютере,
        в качестве параметра передается имя папки. По умолчанию - 'Photo from Insta'. В качестве имени файла
        будет использовано id фотографии."""
        all_photo = self._all_media_info()
        os.mkdir(dir_name)
        os.chdir(dir_name)
        for name_photo, url_photo in tqdm(all_photo.items()):
            time.sleep(1)
            cont = requests.get(url_photo).content
            with open(f"{name_photo}.jpg", 'wb') as file:
                file.write(cont)
        print(f"{len(all_photo)} photos was success download in to the directory - '{dir_name}'")
        return dir_name

    def _create_folder(self, dir_name):
        """Служебный метод, создающий папку на GOOGLE-диске для последующей загрузки медиа-файлов"""
        headers = {'Authorization': settings.GOOGLE_TOKEN}
        url = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart'
        metadata = {'name': dir_name,
                    'mimeType': 'application/vnd.google-apps.folder'}
        files = {'data': ('metadata', json.dumps(metadata), 'application/json; charset = utf-8')}
        r = requests.post(url, headers=headers, files=files).json()['id']
        return r


    def download_to_google(self, dir_name):
        """Метод, загружающий все фото пользователя инстаграмм в отдельную директории на гугл-диске. В качестве
        параметров передается имя директории на гугл-диске куда произойдет загрука медиа-файлов
        !!!!!!!!!!!!!!!!!!!!ТОКЕН ДЕЙСТВИТЕЛЕН ОДИН ЧАС С МОМЕНТА СОЗДАНИЯ !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"""
        headers = {'Authorization': settings.GOOGLE_TOKEN}
        url = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart'
        self.download_all_photo_from_inst_to_dir()
        all_path = os.getcwd()
        folder_name = self._create_folder(dir_name)
        for photo in os.listdir(all_path):
            metadata = {'name': f'{photo}',
                        'parents': [folder_name]}
            files = {'data': ('metadata', json.dumps(metadata), 'application/json; charset = utf-8'),
                     'file': open(photo, 'rb')}
            r = requests.post(url, headers=headers, files=files)
        return f"{len(os.listdir(all_path))} photos was success download to the Google-disk"

    def create_files_on_Google(self):
        """Метод, загружающий фото из директории на компьютере на Google-диск. Реализован при помощи
        библиотеки PYDrive"""
        drive = GoogleDrive(gauth)
        self.download_all_photo_from_inst_to_dir()
        path = os.getcwd()
        for files in os.listdir(path):
            my_file = drive.CreateFile({'title': f"{files}"})
            my_file.SetContentFile(os.path.join(path, files))
            my_file.Upload()
        return f"{len(os.listdir(path))} photos was download on the Google-disk !"

inst_user = Inst()

if __name__ == '__main__':
    pprint(inst_user.user_info('v11.0', 4873701356030303))
    inst_user.download_all_photo_from_inst_to_dir()
    vk_client.download_to_yandex('begemot_korovin', 'VK photos')
    pprint(vk_client.get_followers_info('davidich1981', 'Followers_100.xlsx'))
    pprint(vk_client.download_all_photos_in_yandex('gchivchyan', 'Photo from all albums VK'))
    pprint(vk_client.get_json_file('begemot_korovin', 'Photo_info'))
    pprint(inst_user.download_to_google('Inst photo'))
    print(inst_user.create_files_on_Google())

