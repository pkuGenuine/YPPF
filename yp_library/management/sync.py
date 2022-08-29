from yp_library.models import Reader, Book, LendRecord
from yp_library.utils import bookreturn_notification

from django.db.models import Max, Q
from django.db import transaction

import pymssql
import os

def update_reader():
    """
    更新读者信息
    """
    with pymssql.connect(server=os.environ["LIB_DB_HOST"], user=os.environ["LIB_DB_USER"], 
                         password= os.environ["LIB_DB_PASSWORD"], database=os.environ["LIB_DB"]) as conn:
        with conn.cursor(as_dict=True) as cursor:
            cursor.execute('SELECT ID,IDCardNo FROM Readers')
            # 暂时采用全部遍历的更新方式，因为存在空缺的数据较多，待书房的数据修订完成后，
            # 可以更改为只考虑新增数据
            with transaction.atomic():
                for row in cursor:
                    Reader.objects.update_or_create(
                        id=row['ID'], 
                        defaults={'student_id': row['IDCardNo']}
                    )


def update_book():
    """
    更新书籍信息
    """
    largest_id = Book.objects.aggregate(Max('id'))
    largest_id = largest_id['id__max'] if largest_id else 0

    with pymssql.connect(server=os.environ["LIB_DB_HOST"], user=os.environ["LIB_DB_USER"], 
                         password= os.environ["LIB_DB_PASSWORD"], database=os.environ["LIB_DB"]) as conn:
        with conn.cursor(as_dict=True) as cursor:
            # 筛选新增数据
            cursor.execute(f'''SELECT MarcID,Title,Author,Publisher,ReqNo
                            FROM CircMarc WHERE MarcID>{largest_id}''')
            new_books = []
            for row in cursor:
                new_books.append(
                    Book(
                        id=row['MarcID'],
                        identity_code=row['ReqNo'],
                        title=row['title'],
                        author=row['Author'],
                        publisher=row['Publisher'],
                    )
                )

            with transaction.atomic():
                Book.objects.bulk_create(new_books)


def update_records():
    """
    更新借书记录
    """
    # 本地最新记录的时间
    latest_record_time = LendRecord.objects.aggregate(Max('lend_time'))
    latest_record_time = latest_record_time['lend_time__max'] if latest_record_time else 0
    # 未归还的借书记录
    unreturned_records = LendRecord.objects.filter(returned=False)
    # 转换为方便sql查询的形式
    unreturned_record_id = list(unreturned_records.values_list('id', flat=True))
    unreturned_record_id = ', '.join(list(map(str,unreturned_record_id)))

    with pymssql.connect(server=os.environ["LIB_DB_HOST"], user=os.environ["LIB_DB_USER"], 
                         password= os.environ["LIB_DB_PASSWORD"], database=os.environ["LIB_DB"]) as conn:
        with conn.cursor(as_dict=True) as cursor:
            # 新增借书记录
            cursor.execute(f'''SELECT ID,ReaderID,BarCode,LendTM,DueTm FROM LendHist 
                               WHERE LendTM > convert(datetime, '{latest_record_time.strftime('%Y-%m-%d %H:%M:%S')}')''')
            new_records = []
            for row in cursor:
                new_records.append(
                    LendRecord (
                        id=row['ID'],
                        reader_id_id=row['ReaderID'],
                        book_id_id=int(row['BarCode'].strip()[-5:]),
                        lend_time=row['LendTM'],
                        due_time=row['DueTm']
                    )
                )
            
            with transaction.atomic():
                LendRecord.objects.bulk_create(new_records)

            # 更新未归还记录
            cursor.execute(f'''SELECT ID,IsReturn,ReturnTime
                               FROM LendHist 
                               WHERE ID IN ({unreturned_record_id})''')

            for row in cursor:
                record = unreturned_records.get(id=row['ID'])
                record.returned = True if row['IsReturn'] == 1 else False
                record.return_time = row['ReturnTime']

            with transaction.atomic():
                LendRecord.objects.bulk_update(unreturned_records, fields=['returned', 'return_time'])
    
    # 发送还书提醒
    bookreturn_notification()
    