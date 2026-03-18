# 通用图像分类 MobileNetV2 训练脚本
# 用法: python train/train.py --data_dir /path/to/data --output /path/to/model.pt --epochs 10
import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, models, transforms

PROJECT_ROOT = Path(__file__).parent.parent

train_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.RandomCrop(224),
    transforms.RandomHorizontalFlip(),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def main():
    parser = argparse.ArgumentParser(description="图像分类 MobileNetV2 微调")
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--status_file", type=str, default="")
    args = parser.parse_args()

    start_time = [None]

    def write_status(status: str, epoch: int = 0, total_epochs: int = 0, loss: float = 0, train_acc: float = 0, val_acc: float = 0, message: str = "", batch_idx: int = 0, num_batches: int = 0):
        if not args.status_file:
            return
        if status == "running" and start_time[0] is None:
            start_time[0] = time.time()
        p = Path(args.status_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            obj = {"status": status, "epoch": epoch, "total_epochs": total_epochs, "loss": round(loss, 4),
                   "train_acc": round(train_acc, 4), "val_acc": round(val_acc, 4), "message": message}
            if batch_idx and num_batches > 0:
                obj["batch_idx"] = batch_idx
                obj["num_batches"] = num_batches
            if start_time[0]:
                obj["started_at"] = start_time[0]
            p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_dir}")

    train_path = data_dir / "train" if (data_dir / "train").exists() else data_dir
    class_names = sorted([d.name for d in train_path.iterdir() if d.is_dir()])
    num_classes = len(class_names)
    if num_classes < 2:
        raise ValueError(f"至少需要 2 个类别，当前只有 {num_classes} 个")

    full_dataset = datasets.ImageFolder(str(train_path), transform=train_transform)
    val_size = max(1, int(len(full_dataset) * 0.15))
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)

    weights = models.MobileNet_V2_Weights.IMAGENET1K_V1
    model = models.mobilenet_v2(weights=weights)
    model.classifier[1] = nn.Linear(model.last_channel, num_classes)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    for param in model.features.parameters():
        param.requires_grad = False
    optimizer = torch.optim.Adam(model.classifier.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    num_batches = len(train_loader)
    best_acc = 0.0
    idx_to_class = {str(i): name for i, name in enumerate(class_names)}

    write_status("running", epoch=0, total_epochs=args.epochs, message="训练开始...")
    for epoch in range(args.epochs):
        model.train()
        total_loss, correct, total = 0, 0, 0
        for batch_idx, (images, labels) in enumerate(train_loader):
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            correct += (outputs.argmax(1) == labels).sum().item()
            total += labels.size(0)
            if (batch_idx + 1) % 5 == 0 or batch_idx == num_batches - 1:
                run_loss = total_loss / (batch_idx + 1)
                run_acc = correct / total
                write_status("running", epoch=epoch + 1, total_epochs=args.epochs, loss=run_loss, train_acc=run_acc, batch_idx=batch_idx + 1, num_batches=num_batches)
        train_acc = correct / total
        model.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                val_correct += (outputs.argmax(1) == labels).sum().item()
                val_total += labels.size(0)
        val_acc = val_correct / max(val_total, 1)
        loss_val = total_loss / len(train_loader)
        write_status("running", epoch=epoch + 1, total_epochs=args.epochs, loss=loss_val, train_acc=train_acc, val_acc=val_acc, message=f"Epoch {epoch + 1}/{args.epochs}", batch_idx=num_batches, num_batches=num_batches)
        if val_acc >= best_acc:
            best_acc = val_acc
            torch.save(model, output_path)

    mapping_path = output_path.parent / "class_mapping.json"
    mapping_path.write_text(json.dumps(idx_to_class, ensure_ascii=False, indent=2), encoding="utf-8")
    write_status("done", epoch=args.epochs, total_epochs=args.epochs, val_acc=best_acc, message=f"训练完成，最佳验证准确率: {best_acc:.1%}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import sys
        status_file = ""
        for i, a in enumerate(sys.argv):
            if a == "--status_file" and i + 1 < len(sys.argv):
                status_file = sys.argv[i + 1]
                break
        if status_file:
            Path(status_file).parent.mkdir(parents=True, exist_ok=True)
            Path(status_file).write_text(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False), encoding="utf-8")
        raise
