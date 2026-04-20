FROM odoo:16.0

USER root

RUN pip install pymysql
USER odoo
