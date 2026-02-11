# YOLOv11n

class1_training.pyを実行するとYOLO11n.ptを元にimage，labelの中の画像ファイルとアノテーションデータを用いて学習します<Br><Br>

datasetの形式<Br>

<pre>
├─datasets
│  ├─dataset
│  │  ├─image
│  │  │  ├─train
│  │  │  ├─test
│  │  │  ├─val
│  │  ├─label
│  │  │  ├─train
│  │  │  ├─test
│  │  │  ├─val
│  │  ├─training.yaml
</pre>


- datasetは画像ファイルを格納するimageと対応するファイル名のアノテーションテキストデータのlabelから構成されています<Br>
- trainは学習に使用するデータ<Br>
- testは最終的な評価に使用するデータ(学習には関係ない)<Br>
- valは学習中のモデルの評価に都度使用されるデータ<Br>
- train，test，valのディレクトリ位置がtraining.yamlに記されており，学習時にはtraining.yamlを渡します