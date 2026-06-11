from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, TextAreaField, SubmitField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, NumberRange


class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(1, 80)])
    password = PasswordField('密码', validators=[DataRequired()])
    submit = SubmitField('登录')


class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(2, 80)])
    password = PasswordField('密码', validators=[DataRequired(), Length(4, 100)])
    submit = SubmitField('注册')


class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('当前密码', validators=[DataRequired()])
    new_password = PasswordField('新密码', validators=[DataRequired(), Length(4, 100)])
    submit = SubmitField('修改密码')


class AdminChangePasswordForm(FlaskForm):
    """管理员帮用户改密码"""
    user_id = HiddenField(validators=[DataRequired()])
    new_password = PasswordField('新密码', validators=[DataRequired(), Length(4, 100)])
    submit = SubmitField('修改密码')


class EquipmentForm(FlaskForm):
    name = StringField('器材名称', validators=[DataRequired(), Length(1, 200)])
    model = StringField('型号', validators=[Optional(), Length(0, 200)])
    packaging = StringField('封装', validators=[Optional(), Length(0, 200)])
    category_id = SelectField('分类', coerce=int, validators=[DataRequired()])
    alert_threshold = IntegerField('预警阈值', default=0, validators=[Optional(), NumberRange(min=0)])
    unit = StringField('单位', default='个', validators=[Optional(), Length(0, 50)])
    remark = TextAreaField('备注', validators=[Optional()])
    submit = SubmitField('保存')


class CategoryForm(FlaskForm):
    name = StringField('分类名称', validators=[DataRequired(), Length(1, 80)])
    description = TextAreaField('描述', validators=[Optional()])
    submit = SubmitField('保存')


class StockInForm(FlaskForm):
    equipment_id = SelectField('器材', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('入库数量', validators=[DataRequired(), NumberRange(min=1, message='数量必须大于0')])
    remark = TextAreaField('备注', validators=[Optional()])
    submit = SubmitField('确认入库')


class StockOutForm(FlaskForm):
    equipment_id = SelectField('器材', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('出库数量', validators=[DataRequired(), NumberRange(min=1, message='数量必须大于0')])
    remark = TextAreaField('备注', validators=[Optional()])
    submit = SubmitField('确认出库')


class UserSettingsForm(FlaskForm):
    dark_mode = BooleanField('深色模式')
    items_per_page = SelectField('每页条数', coerce=int, choices=[(10, '10条'), (15, '15条'), (20, '20条'), (30, '30条'), (50, '50条')])
    submit = SubmitField('保存')


class UploadFaviconForm(FlaskForm):
    """管理员上传 favicon"""
    pass  # 直接用 request.files
