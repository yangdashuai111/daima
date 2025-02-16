from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Table # type: ignore
from sqlalchemy.orm import relationship # type: ignore
from sqlalchemy.ext.declarative import declarative_base # type: ignore
from datetime import datetime
import bcrypt

Base = declarative_base()

# 用户-赛道关联表
user_track_association = Table(
    'user_track_association',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('track_id', Integer, ForeignKey('tracks.id'))
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True)
    password_hash = Column(String)
    daily_limit = Column(Integer, default=5)  # 每日可领取数量
    is_admin = Column(Boolean, default=False)  # 是否是管理员
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)
    
    # 关联赛道（多对多）
    authorized_tracks = relationship(
        "Track",
        secondary=user_track_association,
        back_populates="authorized_users"
    )
    
    # 已领取的文章（一对多）
    claimed_articles = relationship("ArticleClaim", back_populates="user")
    
    def set_password(self, password: str):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode(), salt).decode()
    
    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode(),
            self.password_hash.encode()
        )

class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    articles = relationship("Article", back_populates="track")
    # 添加用户关联
    authorized_users = relationship(
        "User",
        secondary=user_track_association,
        back_populates="authorized_tracks"
    )
    # 添加代运营关联
    operators = relationship(
        "Operator",
        secondary="operator_track_association",
        back_populates="managed_tracks"
    )

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    file_path = Column(String)  # 文件路径
    track_id = Column(Integer, ForeignKey("tracks.id"))
    created_at = Column(DateTime, default=datetime.now)
    
    track = relationship("Track", back_populates="articles")
    claims = relationship("ArticleClaim", back_populates="article")

class ArticleClaim(Base):
    __tablename__ = "article_claims"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    article_id = Column(Integer, ForeignKey("articles.id"))
    claimed_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="claimed_articles")
    article = relationship("Article", back_populates="claims")

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    browser_id = Column(Integer, ForeignKey("browsers.id"))
    status = Column(Boolean, default=True)
    
    browser = relationship("Browser", back_populates="accounts")

class Browser(Base):
    __tablename__ = "browsers"

    id = Column(Integer, primary_key=True, index=True)
    browser_name = Column(String, index=True)
    notes = Column(String, nullable=True)
    proxy_ip = Column(String, nullable=True)
    
    accounts = relationship("Account", back_populates="browser")

class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    ai_content = Column(Text, nullable=True)
    status = Column(String, default="未发布")  # 状态：未发布、已发布
    created_at = Column(DateTime, default=datetime.now)
    source_type = Column(String, default="新闻公众号")  # 来源类型

class Operator(Base):
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    name = Column(String)  # 真实姓名
    phone = Column(String)  # 联系电话
    daily_limit = Column(Integer, default=5)  # 每日可领取数量
    status = Column(Boolean, default=True)  # 账号状态：启用/禁用
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)
    
    # 新增字段
    platform = Column(String)  # 平台类型
    account_id = Column(String)  # 账号ID
    appid = Column(String)  # AppID
    register_date = Column(DateTime)  # 注册日期
    is_violation = Column(Boolean, default=False)  # 是否违规
    screenshot_path = Column(String)  # 截图路径
    audit_status = Column(String, default="pending")  # 审核状态: pending-待审核, approved-已通过, rejected-已拒绝
    audit_time = Column(DateTime)  # 审核时间
    audit_remark = Column(String)  # 审核备注
    
    # 关联赛道（多对多）
    managed_tracks = relationship(
        "Track",
        secondary="operator_track_association",
        back_populates="operators"
    )
    
    def set_password(self, password: str):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode(), salt).decode()
    
    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode(),
            self.password_hash.encode()
        )

# 代运营-赛道关联表
operator_track_association = Table(
    'operator_track_association',
    Base.metadata,
    Column('operator_id', Integer, ForeignKey('operators.id')),
    Column('track_id', Integer, ForeignKey('tracks.id'))
) 