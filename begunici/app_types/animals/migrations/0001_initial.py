# Generated by Django 4.2.15 on 2024-12-25 10:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('veterinary', '0003_alter_veterinary_veterinary_care'),
    ]

    operations = [
        migrations.CreateModel(
            name='Lambing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('planned_lambing_date', models.DateField(verbose_name='Планируемая дата окота')),
                ('actual_lambing_date', models.DateField(blank=True, null=True, verbose_name='Фактическая дата окота')),
                ('number_of_lambs', models.IntegerField(blank=True, null=True, verbose_name='Количество ягнят')),
            ],
            options={
                'verbose_name': 'Окот',
                'verbose_name_plural': 'Окоты',
            },
        ),
        migrations.CreateModel(
            name='Maker',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='Дата рождения')),
                ('age', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Возраст (в месяцах)')),
                ('note', models.CharField(blank=True, max_length=100, null=True, verbose_name='Примечание')),
                ('is_archived', models.BooleanField(default=False, verbose_name='В архиве')),
                ('plemstatus', models.CharField(max_length=200, verbose_name='Племенной статус')),
                ('working_condition', models.CharField(max_length=200, verbose_name='Рабочее состояние')),
                ('working_condition_date', models.DateField(blank=True, null=True, verbose_name='Дата установки статуса')),
                ('animal_status', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.status', verbose_name='Статус')),
                ('father', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children_father_maker', to='animals.maker', verbose_name='Отец')),
            ],
            options={
                'verbose_name': 'Производитель',
                'verbose_name_plural': 'Производители',
            },
        ),
        migrations.CreateModel(
            name='Sheep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='Дата рождения')),
                ('age', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Возраст (в месяцах)')),
                ('note', models.CharField(blank=True, max_length=100, null=True, verbose_name='Примечание')),
                ('is_archived', models.BooleanField(default=False, verbose_name='В архиве')),
                ('animal_status', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.status', verbose_name='Статус')),
                ('father', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children_father_sheep', to='animals.maker', verbose_name='Отец')),
                ('lambing_history', models.ManyToManyField(blank=True, related_name='sheep_lambings', to='animals.lambing', verbose_name='История окотов')),
                ('mother', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children_mother_sheep', to='animals.sheep', verbose_name='Мать')),
                ('place', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.place', verbose_name='Место')),
                ('tag', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='veterinary.tag', verbose_name='Бирка')),
                ('veterinary_history', models.ManyToManyField(blank=True, to='veterinary.veterinary', verbose_name='История ветобработок')),
                ('weight_records', models.ManyToManyField(blank=True, to='veterinary.weightrecord', verbose_name='История взвешиваний')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Ram',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='Дата рождения')),
                ('age', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Возраст (в месяцах)')),
                ('note', models.CharField(blank=True, max_length=100, null=True, verbose_name='Примечание')),
                ('is_archived', models.BooleanField(default=False, verbose_name='В архиве')),
                ('animal_status', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.status', verbose_name='Статус')),
                ('father', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children_father_ram', to='animals.maker', verbose_name='Отец')),
                ('mother', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children_mother_ram', to='animals.sheep', verbose_name='Мать')),
                ('place', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.place', verbose_name='Место')),
                ('tag', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='veterinary.tag', verbose_name='Бирка')),
                ('veterinary_history', models.ManyToManyField(blank=True, to='veterinary.veterinary', verbose_name='История ветобработок')),
                ('weight_records', models.ManyToManyField(blank=True, to='veterinary.weightrecord', verbose_name='История взвешиваний')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='maker',
            name='mother',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children_mother_maker', to='animals.sheep', verbose_name='Мать'),
        ),
        migrations.AddField(
            model_name='maker',
            name='place',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.place', verbose_name='Место'),
        ),
        migrations.AddField(
            model_name='maker',
            name='tag',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='veterinary.tag', verbose_name='Бирка'),
        ),
        migrations.AddField(
            model_name='maker',
            name='veterinary_history',
            field=models.ManyToManyField(blank=True, to='veterinary.veterinary', verbose_name='История ветобработок'),
        ),
        migrations.AddField(
            model_name='maker',
            name='weight_records',
            field=models.ManyToManyField(blank=True, to='veterinary.weightrecord', verbose_name='История взвешиваний'),
        ),
        migrations.AddField(
            model_name='lambing',
            name='ewe',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='animals.sheep', verbose_name='Овца (Мать)'),
        ),
        migrations.AddField(
            model_name='lambing',
            name='maker',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='animals.maker', verbose_name='Производитель (Отец)'),
        ),
        migrations.CreateModel(
            name='Ewe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('birth_date', models.DateField(blank=True, null=True, verbose_name='Дата рождения')),
                ('age', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Возраст (в месяцах)')),
                ('note', models.CharField(blank=True, max_length=100, null=True, verbose_name='Примечание')),
                ('is_archived', models.BooleanField(default=False, verbose_name='В архиве')),
                ('animal_status', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.status', verbose_name='Статус')),
                ('father', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children_father_ewe', to='animals.maker', verbose_name='Отец')),
                ('mother', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children_mother_ewe', to='animals.sheep', verbose_name='Мать')),
                ('place', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='veterinary.place', verbose_name='Место')),
                ('tag', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='veterinary.tag', verbose_name='Бирка')),
                ('veterinary_history', models.ManyToManyField(blank=True, to='veterinary.veterinary', verbose_name='История ветобработок')),
                ('weight_records', models.ManyToManyField(blank=True, to='veterinary.weightrecord', verbose_name='История взвешиваний')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
