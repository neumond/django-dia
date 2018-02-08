from django.db import models


# Simple model


class Person(models.Model):
    first_name = models.CharField(max_length=30, verbose_name='First name of a person')
    last_name = models.CharField(max_length=30)


# Abstract model


class AbstractShape(models.Model):
    area = models.FloatField()

    class Meta:
        abstract = True


class Square(AbstractShape):
    side = models.FloatField()


class Circle(AbstractShape):
    radius = models.FloatField()


# Inheritance


class Pet(models.Model):
    name = models.CharField(max_length=100)


class Cat(Pet):
    meows = models.IntegerField()


class Dog(Pet):
    woofs = models.IntegerField()


# 1:n relation


class Post(models.Model):
    content = models.TextField()


class Comment(models.Model):
    post = models.ForeignKey(Post)
    content = models.TextField()


# 1:1 relation


class Automobile(models.Model):
    model = models.CharField(max_length=100)
    year = models.IntegerField()


class Engine(models.Model):
    model = models.CharField(max_length=100)
    automobile = models.OneToOneField(Automobile)


# n:n relation


class Language(models.Model):
    name = models.CharField(max_length=10, unique=True)


class Speaker(models.Model):
    name = models.CharField(max_length=100)
    language = models.ManyToManyField(Language)


# n:n relation with intermediate model


class Picture(models.Model):
    url = models.CharField(max_length=100)


class Like(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)


class Poster(models.Model):
    name = models.CharField(max_length=100)
    likes = models.ManyToManyField(Picture, through=Like)


# self referencing


class Category(models.Model):
    parent = models.ForeignKey('self', null=True)
    name = models.CharField(max_length=100)


class Friend(models.Model):
    friends = models.ManyToManyField('self')
