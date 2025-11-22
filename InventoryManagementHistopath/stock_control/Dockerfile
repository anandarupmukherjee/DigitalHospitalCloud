# FROM python:3.8

# ENV PYTHONDONTWRITEBYTECODE 1
# ENV PYTHONUNBUFFERED 1

# WORKDIR /code

# COPY requirements.txt /code/
# RUN pip install --upgrade pip && pip install -r requirements.txt

# COPY . /code/

# # Ensure staticfiles directory and permissions
# RUN mkdir -p /code/staticfiles && chmod -R 755 /code/staticfiles

# # Copy and set execute permissions for the entrypoint
# COPY entrypoint.sh /code/entrypoint.sh
# RUN chmod +x /code/entrypoint.sh


# Use a Python image compatible with the Raspberry Pi's architecture
FROM python:3.8

# Set environment variables to prevent Python from writing pyc files to disc and buffering stdout and stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /code

# Install dependencies
COPY requirements.txt /code/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . /code/

# RUN python manage.py collectstatic --noinput --verbosity 2
