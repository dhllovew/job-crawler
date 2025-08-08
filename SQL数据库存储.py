import json
import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Enum, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError
import enum
import logging
from typing import List, Dict, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('JobDBManager')

# 数据库配置 - 请修改为你的数据库信息
DB_CONFIG = {
    'user': 'your_username',
    'password': 'your_password',
    'host': 'localhost',
    'port': '3306',
    'database': 'job_db'
}

# 初始化数据库连接
Base = declarative_base()
engine = create_engine(
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"
)
Session = sessionmaker(bind=engine)


# 岗位类型枚举
class JobType(enum.Enum):
    campus = "校招"
    internship = "实习"


# 数据库模型定义
class Job(Base):
    """岗位信息主表"""
    __tablename__ = "jobs"
    
    id = Column(String(100), primary_key=True)  # 使用JSON中的key作为主键
    job_type = Column(Enum(JobType), nullable=False)
    company = Column(String(100), nullable=False)
    company_type = Column(String(50))
    location = Column(String(100))
    recruitment_type = Column(String(50))
    target = Column(String(100), nullable=False)
    position = Column(Text, nullable=False)
    update_time = Column(String(50))  # 保留原始字符串格式
    deadline = Column(String(50))     # 保留原始字符串格式
    links = Column(String(255))
    notice = Column(String(255))
    referral = Column(String(100))
    notes = Column(Text)
    crawl_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    # 关联技能标签
    skills = relationship("JobSkill", backref="job", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        index('idx_company', 'company'),
        index('idx_job_type', 'job_type'),
        index('idx_target', 'target'),
        index('idx_crawl_time', 'crawl_time'),
    )


class JobSkill(Base):
    """岗位技能标签表"""
    __tablename__ = "job_skills"
    
    id = Column(String(100), primary_key=True)
    job_id = Column(String(100), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    skill_tag = Column(String(50), nullable=False)
    
    # 索引
    __table_args__ = (
        index('idx_skill_tag', 'skill_tag'),
        index('idx_job_skill', 'job_id', 'skill_tag'),
    )


class JobDBManager:
    """数据库管理类"""
    
    def __init__(self):
        self.session = Session()
        # 创建数据表
        Base.metadata.create_all(engine)
        logger.info("数据库初始化完成，数据表已创建")
    
    def close(self):
        """关闭数据库连接"""
        self.session.close()
        logger.info("数据库连接已关闭")
    
    def extract_skills(self, position: str) -> List[str]:
        """
        从职位描述中提取技能标签
        可根据实际需求扩展关键词库
        """
        skill_keywords = [
            'Python', 'Java', 'C++', 'SQL', '算法', '芯片', '硬件', 
            '软件', '测试', '销售', '职能', '通信', '微波', '计算机',
            '机械', '材料', '产品', '运营', '模拟'
        ]
        
        skills = []
        for keyword in skill_keywords:
            if keyword in position:
                skills.append(keyword)
        
        return list(set(skills))  # 去重
    
    def import_from_json(self, json_file_path: str) -> Dict[str, int]:
        """
        从JSON文件导入数据到数据库
        :param json_file_path: JSON文件路径
        :return: 统计结果 {'total': 总条数, 'added': 新增条数, 'skipped': 跳过条数}
        """
        stats = {'total': 0, 'added': 0, 'skipped': 0}
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            jobs_data = data.get('jobs', {})
            stats['total'] = len(jobs_data)
            logger.info(f"开始导入数据，共 {stats['total']} 条岗位信息")
            
            for job_id, job_info in jobs_data.items():
                # 检查是否已存在
                existing_job = self.session.query(Job).filter_by(id=job_id).first()
                if existing_job:
                    stats['skipped'] += 1
                    continue
                
                try:
                    # 创建岗位记录
                    job_type = JobType.campus if job_info['job_type'] == '校招' else JobType.internship
                    
                    new_job = Job(
                        id=job_id,
                        job_type=job_type,
                        company=job_info['company'],
                        company_type=job_info.get('company_type', ''),
                        location=job_info.get('location', ''),
                        recruitment_type=job_info.get('recruitment_type', ''),
                        target=job_info['target'],
                        position=job_info['position'],
                        update_time=job_info.get('update_time', ''),
                        deadline=job_info.get('deadline', ''),
                        links=job_info.get('links', ''),
                        notice=job_info.get('notice', ''),
                        referral=job_info.get('referral', ''),
                        notes=job_info.get('notes', ''),
                        crawl_time=datetime.datetime.fromisoformat(job_info['crawl_time'])
                    )
                    
                    # 提取并添加技能标签
                    skills = self.extract_skills(job_info['position'])
                    for skill in skills:
                        skill_id = f"{job_id}-{skill}"
                        new_job.skills.append(JobSkill(id=skill_id, skill_tag=skill))
                    
                    self.session.add(new_job)
                    self.session.commit()
                    stats['added'] += 1
                    logger.debug(f"成功导入: {job_id}")
                
                except IntegrityError as e:
                    self.session.rollback()
                    stats['skipped'] += 1
                    logger.warning(f"数据冲突，跳过导入: {job_id}, 错误: {str(e)}")
                except Exception as e:
                    self.session.rollback()
                    stats['skipped'] += 1
                    logger.error(f"导入失败: {job_id}, 错误: {str(e)}")
            
            logger.info(f"数据导入完成 - 总条数: {stats['total']}, 新增: {stats['added']}, 跳过: {stats['skipped']}")
            return stats
            
        except FileNotFoundError:
            logger.error(f"JSON文件不存在: {json_file_path}")
            raise
        except json.JSONDecodeError:
            logger.error(f"JSON文件格式错误: {json_file_path}")
            raise
        except Exception as e:
            logger.error(f"导入数据时发生错误: {str(e)}")
            raise
    
    def query_jobs(self, 
                  job_type: Optional[str] = None,
                  target: Optional[str] = None,
                  location: Optional[str] = None,
                  skill: Optional[str] = None) -> List[Job]:
        """
        查询岗位信息
        :param job_type: 岗位类型（校招/实习）
        :param target: 招聘对象（如"2026年毕业生"）
        :param location: 工作地点
        :param skill: 技能要求
        :return: 岗位列表
        """
        query = self.session.query(Job)
        
        # 应用筛选条件
        if job_type:
            job_type_enum = JobType.campus if job_type == '校招' else JobType.internship
            query = query.filter(Job.job_type == job_type_enum)
        
        if target:
            query = query.filter(Job.target.like(f"%{target}%"))
        
        if location:
            query = query.filter(Job.location.like(f"%{location}%"))
        
        if skill:
            query = query.join(JobSkill).filter(JobSkill.skill_tag == skill)
        
        # 按爬取时间倒序
        query = query.order_by(Job.crawl_time.desc())
        
        results = query.all()
        logger.info(f"查询完成，找到 {len(results)} 条匹配记录")
        return results
    
    def clean_expired_jobs(self, days: int = 30) -> int:
        """
        清理过期岗位（已截止且超过指定天数）
        :param days: 过期天数阈值
        :return: 清理的记录数
        """
        threshold_date = datetime.datetime.now() - datetime.timedelta(days=days)
        
        # 查询要删除的岗位
        expired_jobs = self.session.query(Job)\
            .filter(
                Job.deadline != "招满为止",
                Job.crawl_time < threshold_date
            ).all()
        
        if not expired_jobs:
            logger.info("没有需要清理的过期岗位")
            return 0
        
        # 执行删除
        deleted_count = len(expired_jobs)
        for job in expired_jobs:
            self.session.delete(job)
        
        self.session.commit()
        logger.info(f"已清理 {deleted_count} 条过期岗位记录")
        return deleted_count


# 示例用法
if __name__ == "__main__":
    # 初始化数据库管理器
    db_manager = JobDBManager()
    
    try:
        # 从JSON文件导入数据
        json_path = "jobs.json"  # 替换为你的JSON文件路径
        import_stats = db_manager.import_from_json(json_path)
        print(f"数据导入统计: {import_stats}")
        
        # 示例查询: 2026届校招，包含"算法"技能的岗位
        print("\n查询2026届校招，包含'算法'技能的岗位:")
        jobs = db_manager.query_jobs(
            job_type="校招",
            target="2026",
            skill="算法"
        )
        
        for job in jobs:
            print(f"\n公司: {job.company}")
            print(f"职位: {job.position}")
            print(f"地点: {job.location}")
            print(f"截止时间: {job.deadline}")
            print(f"技能要求: {[s.skill_tag for s in job.skills]}")
            print(f"详情链接: {job.links}")
        
        # 清理30天前的过期岗位
        # deleted = db_manager.clean_expired_jobs(days=30)
        # print(f"\n清理了 {deleted} 条过期岗位记录")
        
    finally:
        # 关闭数据库连接
        db_manager.close()
    
