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
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    content = models.TextField()


# 1:1 relation


class Automobile(models.Model):
    model = models.CharField(max_length=100)
    year = models.IntegerField()


class Engine(models.Model):
    model = models.CharField(max_length=100)
    automobile = models.OneToOneField(Automobile, on_delete=models.CASCADE)


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
    picture = models.ForeignKey(Picture, on_delete=models.CASCADE)
    poster = models.ForeignKey('Poster', on_delete=models.CASCADE)


class Poster(models.Model):
    name = models.CharField(max_length=100)
    likes = models.ManyToManyField(Picture, through=Like)


# n:n relation with intermediate model with specified field


class Picture2(models.Model):
    url = models.CharField(max_length=100)


class Poster2(models.Model):
    name = models.CharField(max_length=100)
    likes = models.ManyToManyField(
        Picture2,
        through='Like2',
        through_fields=('poster', 'picture'),
    )


class Like2(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    picture = models.ForeignKey(Picture2, on_delete=models.CASCADE)
    poster = models.ForeignKey(Poster2, on_delete=models.CASCADE)


# self referencing


class Category(models.Model):
    parent = models.ForeignKey('self', null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class Friend(models.Model):
    friends = models.ManyToManyField('self')


# relation from abstract model


class Shop(models.Model):
    name = models.CharField(max_length=100)


class AbstractGoods(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class GroceryGoods(AbstractGoods):
    weight = models.FloatField()


class ProxyShop(Shop):
    class Meta:
        proxy = True
